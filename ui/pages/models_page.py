from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QProgressBar, QScrollArea, QTabWidget,
    QVBoxLayout, QWidget,
)

from ui.workers import DeleteModelWorker, ModelListWorker, PullWorker


FEATURED_MODELS = [
    ("qwen3:4b", "Qwen 3", "A compact general-purpose model for everyday chat, reasoning and multilingual tasks.", "General purpose", "4B"),
    ("llama3.2:3b", "Llama 3.2", "A lightweight assistant model with a good balance of speed and capability.", "Fast", "3B"),
    ("gemma3:4b", "Gemma 3", "A capable small model for chat, instruction following and multimodal workflows.", "General purpose", "4B"),
    ("deepseek-r1:7b", "DeepSeek R1", "A reasoning-focused model for step-by-step problem solving.", "Reasoning", "7B"),
    ("qwen2.5-coder:7b", "Qwen 2.5 Coder", "A coding-oriented model for explanations, debugging and code generation.", "Coding", "7B"),
    ("mistral:7b", "Mistral", "A well-known general assistant model for local experimentation.", "General purpose", "7B"),
    ("nomic-embed-text", "Nomic Embed Text", "An embedding model for semantic search and retrieval projects.", "Embeddings", "Embedding"),
]


def format_bytes(value: int | float | None) -> str:
    if value is None:
        return "—"
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TB"


class DownloadJobCard(QFrame):
    def __init__(self, model_name: str) -> None:
        super().__init__()
        self.setObjectName("ModelCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        top = QHBoxLayout()
        self.name_label = QLabel(model_name)
        self.name_label.setObjectName("CardTitle")
        self.status_label = QLabel("Preparing download…")
        self.status_label.setObjectName("Muted")
        top.addWidget(self.name_label)
        top.addStretch()
        top.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        bottom = QHBoxLayout()
        self.detail_label = QLabel("Waiting for Ollama")
        self.detail_label.setObjectName("Muted")
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("Muted")
        bottom.addWidget(self.detail_label)
        bottom.addStretch()
        bottom.addWidget(self.percent_label)
        layout.addLayout(top)
        layout.addWidget(self.progress)
        layout.addLayout(bottom)

    def update_event(self, event: dict) -> None:
        status = str(event.get("status", "Downloading"))
        current = event.get("completed")
        total = event.get("total")
        self.status_label.setText(status)
        if isinstance(current, (int, float)) and isinstance(total, (int, float)) and total > 0:
            percent = max(0, min(100, int(current * 100 / total)))
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
            self.percent_label.setText(f"{percent}%")
            self.detail_label.setText(f"{format_bytes(current)} of {format_bytes(total)}")
        else:
            self.progress.setRange(0, 0)
            self.percent_label.setText("Working")
            self.detail_label.setText(status)

    def finish(self, success: bool, message: str = "") -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if success else self.progress.value())
        self.status_label.setText("Downloaded" if success else "Failed")
        self.detail_label.setText(message or ("Model is ready to use." if success else "Check the error details."))
        self.percent_label.setText("100%" if success else "—")


class ModelsPage(QWidget):
    models_changed = Signal(list)
    connection_changed = Signal(bool)
    status_message = Signal(str)

    def __init__(self, endpoint: str, parent=None) -> None:
        super().__init__(parent)
        self.endpoint = endpoint
        self.models: list[dict] = []
        self.workers: dict[str, PullWorker] = {}
        self.jobs: dict[str, DownloadJobCard] = {}
        self.list_worker: ModelListWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 27, 34, 24)
        root.setSpacing(15)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("Models")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Discover, download and manage models available through Ollama.")
        subtitle.setObjectName("PageSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()
        self.refresh_button = QPushButton("↻  Refresh library")
        self.refresh_button.clicked.connect(self.refresh_models)
        header.addWidget(self.refresh_button)
        root.addLayout(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.discover_tab = QWidget()
        self.library_tab = QWidget()
        self.tabs.addTab(self.discover_tab, "Discover")
        self.tabs.addTab(self.library_tab, "My models")
        self._build_discover()
        self._build_library()

        self.downloads_frame = QFrame()
        self.downloads_frame.setObjectName("Surface")
        downloads_layout = QVBoxLayout(self.downloads_frame)
        downloads_layout.setContentsMargins(15, 12, 15, 13)
        downloads_layout.setSpacing(9)
        downloads_header = QHBoxLayout()
        downloads_title = QLabel("Download activity")
        downloads_title.setObjectName("SectionTitle")
        self.active_count = QLabel("No active downloads")
        self.active_count.setObjectName("Muted")
        downloads_header.addWidget(downloads_title)
        downloads_header.addStretch()
        downloads_header.addWidget(self.active_count)
        downloads_layout.addLayout(downloads_header)
        self.jobs_layout = QVBoxLayout()
        self.jobs_layout.setSpacing(8)
        downloads_layout.addLayout(self.jobs_layout)
        root.addWidget(self.downloads_frame)
        self.refresh_models()

    def set_endpoint(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def _build_discover(self) -> None:
        layout = QVBoxLayout(self.discover_tab)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(13)
        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(19, 15, 19, 15)
        hero_title = QLabel("Find a model for your workflow")
        hero_title.setObjectName("CardTitle")
        hero_copy = QLabel("Start with a popular model below, or enter any model name or tag from the Ollama library.")
        hero_copy.setObjectName("CardDescription")
        hero_copy.setWordWrap(True)
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_copy)
        layout.addWidget(hero)

        custom_row = QHBoxLayout()
        self.custom_model_input = QLineEdit()
        self.custom_model_input.setPlaceholderText("Model name or tag, e.g. qwen3:8b or llama3.2:3b")
        self.custom_model_input.returnPressed.connect(self._pull_custom)
        self.custom_pull_button = QPushButton("＋  Download model")
        self.custom_pull_button.setObjectName("PrimaryButton")
        self.custom_pull_button.clicked.connect(self._pull_custom)
        custom_row.addWidget(self.custom_model_input, 1)
        custom_row.addWidget(self.custom_pull_button)
        layout.addLayout(custom_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.catalog_grid = QGridLayout(content)
        self.catalog_grid.setContentsMargins(1, 2, 1, 2)
        self.catalog_grid.setHorizontalSpacing(12)
        self.catalog_grid.setVerticalSpacing(12)
        for index, (tag, name, description, category, size) in enumerate(FEATURED_MODELS):
            card = QFrame()
            card.setObjectName("ModelCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(15, 14, 15, 14)
            card_layout.setSpacing(8)
            title_row = QHBoxLayout()
            model_title = QLabel(name)
            model_title.setObjectName("CardTitle")
            tag_label = QLabel(size)
            tag_label.setObjectName("Tag")
            title_row.addWidget(model_title)
            title_row.addStretch()
            title_row.addWidget(tag_label)
            description_label = QLabel(description)
            description_label.setObjectName("CardDescription")
            description_label.setWordWrap(True)
            category_label = QLabel(category)
            category_label.setObjectName("Muted")
            download = QPushButton("Download  ↓")
            download.clicked.connect(lambda _checked=False, model=tag: self.start_download(model))
            card_layout.addLayout(title_row)
            card_layout.addWidget(description_label, 1)
            card_layout.addWidget(category_label)
            card_layout.addWidget(download)
            self.catalog_grid.addWidget(card, index // 2, index % 2)
        self.catalog_grid.setRowStretch((len(FEATURED_MODELS) + 1) // 2, 1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    def _build_library(self) -> None:
        layout = QVBoxLayout(self.library_tab)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(8)
        note = QLabel("Models installed in the Ollama server connected to this app.")
        note.setObjectName("Muted")
        layout.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.library_content = QWidget()
        self.library_layout = QVBoxLayout(self.library_content)
        self.library_layout.setContentsMargins(0, 4, 8, 4)
        self.library_layout.setSpacing(9)
        self.library_empty = QLabel("No models found. Download one from Discover to get started.")
        self.library_empty.setObjectName("Muted")
        self.library_layout.addWidget(self.library_empty)
        self.library_layout.addStretch(1)
        scroll.setWidget(self.library_content)
        layout.addWidget(scroll, 1)

    def _pull_custom(self) -> None:
        model = self.custom_model_input.text().strip()
        if model:
            self.start_download(model)
            self.custom_model_input.clear()

    def start_download(self, model_name: str) -> None:
        model_name = model_name.strip()
        if not model_name:
            return
        if model_name in self.workers and self.workers[model_name].isRunning():
            self.status_message.emit(f"A download for {model_name} is already in progress.")
            return
        if any((item.get("name") or item.get("model")) == model_name for item in self.models):
            self.status_message.emit(f"{model_name} is already installed.")
            self.tabs.setCurrentWidget(self.library_tab)
            return
        card = DownloadJobCard(model_name)
        self.jobs_layout.addWidget(card)
        self.jobs[model_name] = card
        worker = PullWorker(self.endpoint, model_name)
        self.workers[model_name] = worker
        worker.progress.connect(lambda event, name=model_name: self._on_progress(name, event))
        worker.completed.connect(lambda name: self._on_download_completed(name))
        worker.failed.connect(lambda error, name=model_name: self._on_download_failed(name, error))
        worker.finished.connect(lambda name=model_name: self._cleanup_worker(name))
        worker.start()
        self._update_active_count()
        self.status_message.emit(f"Started downloading {model_name}.")

    def _on_progress(self, model_name: str, event: dict) -> None:
        if model_name in self.jobs:
            self.jobs[model_name].update_event(event)

    def _on_download_completed(self, model_name: str) -> None:
        if model_name in self.jobs:
            self.jobs[model_name].finish(True)
        self.status_message.emit(f"{model_name} is ready to use.")
        self.refresh_models()

    def _on_download_failed(self, model_name: str, error: str) -> None:
        if model_name in self.jobs:
            self.jobs[model_name].finish(False, error)
        self.status_message.emit(f"Download failed for {model_name}: {error}")

    def _cleanup_worker(self, model_name: str) -> None:
        worker = self.workers.pop(model_name, None)
        if worker:
            worker.deleteLater()
        self._update_active_count()

    def _update_active_count(self) -> None:
        active = sum(worker.isRunning() for worker in self.workers.values())
        self.active_count.setText(f"{active} active" if active else "No active downloads")

    def refresh_models(self) -> None:
        if self.list_worker and self.list_worker.isRunning():
            return
        self.refresh_button.setEnabled(False)
        worker = ModelListWorker(self.endpoint)
        self.list_worker = worker
        worker.loaded.connect(self._on_models_loaded)
        worker.failed.connect(self._on_models_failed)
        worker.finished.connect(lambda current=worker: self._list_worker_finished(current))
        worker.start()

    def _list_worker_finished(self, worker: ModelListWorker) -> None:
        if self.list_worker is worker:
            self.list_worker = None
        self.refresh_button.setEnabled(True)
        worker.deleteLater()

    def _on_models_loaded(self, models: list[dict]) -> None:
        self.models = models
        self._render_library()
        self.models_changed.emit(models)
        self.connection_changed.emit(True)

    def _on_models_failed(self, error: str) -> None:
        self.status_message.emit(error)
        self.models_changed.emit([])
        self.connection_changed.emit(False)

    def _render_library(self) -> None:
        while self.library_layout.count() > 2:
            item = self.library_layout.takeAt(1)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.library_empty.setVisible(not self.models)
        for model in self.models:
            name = str(model.get("name") or model.get("model") or "Unknown model")
            size = format_bytes(model.get("size"))
            modified = model.get("modified_at", "")
            try:
                modified_label = datetime.fromisoformat(modified.replace("Z", "+00:00")).strftime("Updated %b %d, %Y")
            except (ValueError, AttributeError):
                modified_label = "Installed locally"
            card = QFrame()
            card.setObjectName("ModelCard")
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 11, 14, 11)
            info = QVBoxLayout()
            title = QLabel(name)
            title.setObjectName("CardTitle")
            detail = QLabel(f"{size}   ·   {modified_label}")
            detail.setObjectName("Muted")
            info.addWidget(title)
            info.addWidget(detail)
            remove = QPushButton("Remove")
            remove.setObjectName("DangerButton")
            remove.clicked.connect(lambda _checked=False, value=name: self.remove_model(value))
            row.addLayout(info, 1)
            row.addWidget(remove)
            self.library_layout.insertWidget(self.library_layout.count() - 1, card)

    def remove_model(self, model_name: str) -> None:
        answer = QMessageBox.question(
            self, "Remove model", f"Remove {model_name} from this Ollama installation?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        worker = DeleteModelWorker(self.endpoint, model_name, self)
        worker.completed.connect(lambda: self._after_delete(model_name))
        worker.failed.connect(lambda error: self.status_message.emit(error))
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self.status_message.emit(f"Removing {model_name}…")

    def _after_delete(self, model_name: str) -> None:
        self.status_message.emit(f"Removed {model_name}.")
        self.refresh_models()
