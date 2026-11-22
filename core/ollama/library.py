"""Read the public model catalog and tag variants from the official Ollama website."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import quote, urljoin

import requests


OLLAMA_LIBRARY_URL = "https://ollama.com"

_SEARCH_CARD_RE = re.compile(r"(?s)<li x-test-model\b.*?</li>")
_SEARCH_TITLE_RE = re.compile(r"(?s)<span x-test-search-response-title>(.*?)</span>")
_SEARCH_DESC_RE = re.compile(r'(?s)<p class="max-w-lg[^"]*">(.*?)</p>')
_SEARCH_HREF_RE = re.compile(r'(?s)<a href="([^"]+)" class="group w-full">')
_PULL_COUNT_RE = re.compile(r"(?s)<span x-test-pull-count>(.*?)</span>")
_TAG_COUNT_RE = re.compile(r"(?s)<span x-test-tag-count>(.*?)</span>")
_UPDATED_RE = re.compile(r"(?s)<span x-test-updated>(.*?)</span>")
_NEXT_SEARCH_RE = re.compile(r'hx-get="([^"]*/search\?page=(\d+)[^"]*)"')
_TAG_ROW_SPLIT_RE = re.compile(r'<div class="group px-4 py-3">')
_TAG_MODEL_ROW_SPLIT_RE = re.compile(r'(?s)<div class="hidden group px-4 py-3[^"]*">')
_TAG_COMMAND_RE = re.compile(r'(?s)<input class="command hidden" value="([^"]+)"')
_TAG_HREF_RE = re.compile(r'href="/([^"?#]+:[^"?#]+)"')
_TAG_SIZE_CONTEXT_RE = re.compile(
    r'(?s)<p class="col-span-2 text-neutral-500 text-\[13px\]">([^<]+)</p>'
)
_TAG_INPUT_RE = re.compile(
    r'(?s)<div class="col-span-2 text-neutral-500 text-\[13px\]\s*">\s*(.*?)\s*</div>'
)
_TAG_DIGEST_UPDATED_RE = re.compile(
    r'(?s)<span class="font-mono text-\[11px\]">([^<]+)</span>&nbsp;·&nbsp;([^<]+)'
)
_TAG_LATEST_RE = re.compile(r"(?s)rounded-full[^>]*>\s*latest\s*</span>")
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _clean(value: str) -> str:
    value = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", value)
    value = _TAG_RE.sub(" ", value)
    value = html.unescape(value).replace("\u00a0", " ")
    return _SPACE_RE.sub(" ", value).strip()


def parse_search_results(body: str) -> list[dict[str, Any]]:
    """Parse model-family cards from Ollama's public search HTML."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in _SEARCH_CARD_RE.findall(body):
        name = _clean(_SEARCH_TITLE_RE.search(card).group(1)) if _SEARCH_TITLE_RE.search(card) else ""
        if not name or name in seen:
            continue
        seen.add(name)
        href = _SEARCH_HREF_RE.search(card)
        summary = _SEARCH_DESC_RE.search(card)
        pulls = _PULL_COUNT_RE.search(card)
        tag_count = _TAG_COUNT_RE.search(card)
        updated = _UPDATED_RE.search(card)
        results.append({
            "name": name,
            "summary": _clean(summary.group(1)) if summary else "",
            "path": html.unescape(href.group(1)) if href else f"/library/{name}",
            "downloads": _clean(pulls.group(1)) if pulls else "",
            "tag_count": _clean(tag_count.group(1)) if tag_count else "",
            "updated": _clean(updated.group(1)) if updated else "",
        })
    return results


def next_search_path(body: str, current_page: int) -> str | None:
    """Return the next HTMX search page advertised by Ollama, if any."""
    candidates: list[tuple[int, str]] = []
    for raw_path, raw_page in _NEXT_SEARCH_RE.findall(body):
        try:
            page = int(raw_page)
        except ValueError:
            continue
        if page > current_page:
            candidates.append((page, html.unescape(raw_path)))
    return min(candidates, default=(0, ""))[1] or None


def _base_model_name(reference: str) -> str:
    return reference.strip().lstrip("/").split(":", 1)[0]


def parse_model_tags(body: str, model_name: str) -> list[dict[str, Any]]:
    """Parse every downloadable tag and its published metadata for a model family."""
    prefix = _base_model_name(model_name) + ":"
    tags: list[dict[str, Any]] = []
    seen: set[str] = set()

    parts = _TAG_ROW_SPLIT_RE.split(body)
    if len(parts) <= 1:
        parts = _TAG_MODEL_ROW_SPLIT_RE.split(body)

    for part in parts[1:]:
        command = _TAG_COMMAND_RE.search(part)
        href = _TAG_HREF_RE.search(part)
        reference = html.unescape(command.group(1).strip()) if command else (
            html.unescape(href.group(1).strip()) if href else ""
        )
        reference = reference.lstrip("/")
        if reference.startswith("library/"):
            reference = reference[len("library/"):]
        if not reference.startswith(prefix):
            continue
        tag_name = reference[len(prefix):]
        if not tag_name or tag_name in seen:
            continue
        seen.add(tag_name)

        size_context = _TAG_SIZE_CONTEXT_RE.findall(part)
        size = _clean(size_context[0]) if size_context else ""
        context = _clean(size_context[1]) if len(size_context) > 1 else ""
        input_match = _TAG_INPUT_RE.search(part)
        digest_updated = _TAG_DIGEST_UPDATED_RE.search(part)
        tags.append({
            "tag": tag_name,
            "reference": reference,
            "size": size,
            "context": context,
            "input": _clean(input_match.group(1)) if input_match else "",
            "digest": _clean(digest_updated.group(1)) if digest_updated else "",
            "updated": _clean(digest_updated.group(2)) if digest_updated else "",
            "latest": bool(_TAG_LATEST_RE.search(part)) or tag_name == "latest",
        })
    return tags


class OllamaLibraryClient:
    """Fetch model families and exact variants from ollama.com, not the local daemon."""

    def __init__(self, timeout: float = 25.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Ollama-Sentinel/0.3",
            "Accept": "text/html,application/xhtml+xml",
        })

    def _get(self, path: str) -> str:
        url = urljoin(OLLAMA_LIBRARY_URL, path)
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return response.text

    def list_models(self, max_pages: int = 80) -> list[dict[str, Any]]:
        """Load all model families advertised by Ollama's paginated search page."""
        path = "/search"
        page = 1
        seen: set[str] = set()
        models: list[dict[str, Any]] = []
        for _ in range(max_pages):
            body = self._get(path)
            for item in parse_search_results(body):
                name = item["name"]
                if name not in seen:
                    seen.add(name)
                    models.append(item)
            next_path = next_search_path(body, page)
            if not next_path:
                break
            match = re.search(r"[?&]page=(\d+)", next_path)
            if not match:
                break
            next_page = int(match.group(1))
            if next_page <= page:
                break
            page, path = next_page, next_path
        return models

    def list_tags(self, model_name: str) -> list[dict[str, Any]]:
        """Load the model family's available tags; fall back to its model page."""
        model_path = quote(_base_model_name(model_name), safe="/")
        if "/" in model_path:
            tags_path = f"/{model_path}/tags"
            fallback_path = f"/{model_path}"
        else:
            tags_path = f"/library/{model_path}/tags"
            fallback_path = f"/library/{model_path}"
        try:
            body = self._get(tags_path)
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            body = self._get(fallback_path)
        return parse_model_tags(body, model_name)

    def close(self) -> None:
        self.session.close()
