"""Safe extraction of image and document attachments for multimodal chat."""

from __future__ import annotations

import base64
import csv
import io
import json
import mimetypes
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 80_000
MAX_PDF_PAGES = 100
MAX_SPREADSHEET_ROWS = 1500

IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".jsonl",
    ".html", ".htm", ".xml", ".yaml", ".yml", ".toml", ".ini", ".log",
    ".py", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".h",
    ".cpp", ".hpp", ".cs", ".go", ".rs", ".sql", ".css", ".scss",
    ".sh", ".bash", ".ps1", ".bat", ".cmd", ".ipynb", ".env",
}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xlsm", ".pptx"}
SUPPORTED_EXTENSIONS = IMAGE_TYPES.keys() | TEXT_EXTENSIONS | DOCUMENT_EXTENSIONS


class AttachmentError(ValueError):
    """Raised when an attachment is unsupported, unreadable, or too large."""


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AttachmentError("Could not decode this text file.")


def _extract_text(path: Path, data: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        text = _decode_text(data)
        if suffix in {".html", ".htm", ".xml"}:
            parser = _TextHTMLParser()
            parser.feed(text)
            text = "\n".join(parser.parts)
        elif suffix == ".csv":
            rows = csv.reader(io.StringIO(text))
            text = "\n".join(" | ".join(cell for cell in row) for row in rows)
        elif suffix == ".tsv":
            rows = csv.reader(io.StringIO(text), delimiter="\t")
            text = "\n".join(" | ".join(cell for cell in row) for row in rows)
        elif suffix == ".ipynb":
            try:
                notebook = json.loads(text)
                cells = notebook.get("cells", [])
                text = "\n\n".join(
                    "".join(cell.get("source", []))
                    for cell in cells if cell.get("cell_type") in {"markdown", "code"}
                )
            except (ValueError, AttributeError, TypeError):
                pass
        return text

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise AttachmentError("This PDF is password-protected and cannot be read.")
            pages = reader.pages[:MAX_PDF_PAGES]
            text = "\n\n".join(
                f"[Page {index + 1}]\n{page.extract_text() or ''}"
                for index, page in enumerate(pages)
            )
            if len(reader.pages) > MAX_PDF_PAGES:
                text += f"\n\n[Only the first {MAX_PDF_PAGES} pages were extracted.]"
            if not text.strip():
                raise AttachmentError("No selectable text was found in this PDF. Scanned PDFs need OCR first.")
            return text
        except AttachmentError:
            raise
        except Exception as exc:
            raise AttachmentError(f"Could not read this PDF: {exc}") from exc

    if suffix == ".docx":
        try:
            from docx import Document
            document = Document(io.BytesIO(data))
            parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
            for table in document.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text.strip() for cell in row.cells))
            return "\n".join(parts)
        except Exception as exc:
            raise AttachmentError(f"Could not read this Word document: {exc}") from exc

    if suffix in {".xlsx", ".xlsm"}:
        try:
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            parts: list[str] = []
            try:
                for sheet in workbook.worksheets:
                    parts.append(f"[Sheet: {sheet.title}]")
                    for row_index, row in enumerate(sheet.iter_rows(values_only=True)):
                        if row_index >= MAX_SPREADSHEET_ROWS:
                            parts.append("[Further rows omitted.]")
                            break
                        values = ["" if value is None else str(value) for value in row]
                        if any(values):
                            parts.append(" | ".join(values))
            finally:
                workbook.close()
            return "\n".join(parts)
        except Exception as exc:
            raise AttachmentError(f"Could not read this spreadsheet: {exc}") from exc

    if suffix == ".pptx":
        try:
            from pptx import Presentation
            presentation = Presentation(io.BytesIO(data))
            parts = []
            for index, slide in enumerate(presentation.slides, start=1):
                parts.append(f"[Slide {index}]")
                for shape in slide.shapes:
                    if getattr(shape, "has_text_frame", False) and shape.text.strip():
                        parts.append(shape.text.strip())
                    if getattr(shape, "has_table", False):
                        for row in shape.table.rows:
                            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
            return "\n".join(parts)
        except Exception as exc:
            raise AttachmentError(f"Could not read this presentation: {exc}") from exc

    raise AttachmentError(f"Unsupported file type: {suffix or 'no extension'}")


def prepare_attachment(file_path: str | Path) -> dict[str, Any]:
    """Read a user-selected file, returning either an image payload or extracted text."""
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise AttachmentError("The selected file does not exist or is not a regular file.")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise AttachmentError(f"Unsupported format: {suffix or 'no extension'}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise AttachmentError(f"Could not access the selected file: {exc}") from exc
    if size <= 0:
        raise AttachmentError("The selected file is empty.")
    if size > MAX_FILE_BYTES:
        raise AttachmentError("Each attachment must be 20 MB or smaller.")

    try:
        data = path.read_bytes()
    except OSError as exc:
        raise AttachmentError(f"Could not read {path.name}: {exc}") from exc

    common = {
        "name": path.name,
        "path": str(path),
        "size": size,
        "extension": suffix,
    }
    if suffix in IMAGE_TYPES:
        return {
            **common,
            "kind": "image",
            "mime_type": IMAGE_TYPES[suffix],
            "data": base64.b64encode(data).decode("ascii"),
        }

    text = _extract_text(path, data).strip()
    if not text:
        raise AttachmentError("No readable text was found in this file.")
    was_truncated = len(text) > MAX_TEXT_CHARS
    if was_truncated:
        text = text[:MAX_TEXT_CHARS] + "\n\n[Attachment text truncated to fit the chat context.]"
    return {
        **common,
        "kind": "file",
        "mime_type": mimetypes.guess_type(path.name)[0] or "text/plain",
        "text": text,
        "truncated": was_truncated,
    }
