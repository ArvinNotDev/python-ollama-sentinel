from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QProgressBar,
    QScrollArea, QTabWidget, QVBoxLayout, QWidget, QAbstractItemView,
)

from ui.workers import (
    DeleteModelWorker, ModelListWorker, OllamaCatalogWorker,
    OllamaModelTagsWorker, PullWorker,
)
from ui.theme import app_icon


def format_bytes(value: int | float | None) -> str:
    if value is None:
        return "—"
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TB"


def _variant_label(model_name: str, item: dict[str, Any]) -> str:
    tag = str(item.get("tag") or "latest")
    full_name = str(item.get("reference") or f"{model_name}:{tag}")
    size_match = re.search(r"(?i)(?:^|-)(\d+(?:\.\d+)?[bm])(?:-|$)", tag)
    quant_match = re.search(r"(?i)(?:^|-)((?:i?q\d+_[a-z0-9_]+)|fp16|bf16|f16)(?:-|$)", tag)
    parts = [full_name]
    if size_match:
        parts.append(size_match.group(1).upper())
    if quant_match:
        parts.append(quant_match.group(1).upper())
    if item.get("size"):
        parts.append(str(item["size"]))
    if item.get("context"):
        parts.append(f'{item["context"]} context')
    return "  ·  ".join(parts)


class DownloadJobCard(QFrame):
    cancel_requested = Signal(str)

    def __init__(self, model_name: str) -> None:
        super().__init__()
        self.model_name = model_name
        self._terminal = False
        self.setObjectName("ModelCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 12, 13, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.name_label = QLabel(model_name)
        self.name_label.setObjectName("CardTitle")
        self.name_label.setWordWrap(True)
        self.status_label = QLabel("Preparing…")
        self.status_label.setObjectName("Muted")
        self.cancel_button = QPushButton()
        self.cancel_button.setIcon(app_icon("mdi6.close", "#F09BA4"))
        self.cancel_button.setObjectName("GhostButton")
        self.cancel_button.setFixedSize(30, 30)
        self.cancel_button.setToolTip("Cancel download")
        self.cancel_button.clicked.connect(lambda: self.cancel_requested.emit(self.model_name))
        top.addWidget(self.name_label, 1)
        top.addWidget(self.status_label)
        top.addWidget(self.cancel_button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.layer_progress: dict[str, tuple[int, int]] = {}

        bottom = QHBoxLayout()
        self.detail_label = QLabel("Waiting for Ollama")
        self.detail_label.setObjectName("Muted")
        self.detail_label.setWordWrap(True)
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("Muted")
        bottom.addWidget(self.detail_label, 1)
        bottom.addWidget(self.percent_label)
        layout.addLayout(top)
        layout.addWidget(self.progress)
        layout.addLayout(bottom)
        self.set_compact(False)

    def set_compact(self, compact: bool) -> None:
        self.setMinimumHeight(112 if compact else 150)
        self.progress.setFixedHeight(7 if compact else 10)
        self.layout().setContentsMargins(11 if compact else 13, 9 if compact else 12, 11 if compact else 13, 9 if compact else 12)

    def update_event(self, event: dict) -> None:
        status = str(event.get("status", "Downloading"))
        current = event.get("completed")
        total = event.get("total")
        self.status_label.setText(status)
        if isinstance(current, (int, float)) and isinstance(total, (int, float)) and total > 0:
            layer_id = str(event.get("digest") or status)
            completed = max(0, min(int(current), int(total)))
            self.layer_progress[layer_id] = (completed, int(total))
            overall_completed = sum(item[0] for item in self.layer_progress.values())
            overall_total = sum(item[1] for item in self.layer_progress.values())
            percent = max(0, min(100, int(overall_completed * 100 / overall_total)))
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
            self.percent_label.setText(f"{percent}%")
            self.detail_label.setText(
                f"{format_bytes(overall_completed)} of {format_bytes(overall_total)} downloaded"
            )
        else:
            self.progress.setRange(0, 0)
            self.percent_label.setText("…")
            self.detail_label.setText(status)

    def request_cancel(self) -> None:
        self.cancel_button.setEnabled(False)
        self.cancel_button.setToolTip("Cancelling download…")
        self.status_label.setText("Cancelling…")

    def finish(self, success: bool, message: str = "") -> None:
        self._terminal = True
        self.progress.setRange(0, 100)
        if success:
            self.progress.setValue(100)
            self.status_label.setText("Ready")
            self.detail_label.setText(message or "Model is ready to use.")
            self.percent_label.setText("100%")
        else:
            self.status_label.setText("Failed")
            self.detail_label.setText(message or "Download failed.")
            self.percent_label.setText("—")
        self.cancel_button.hide()

    def finish_cancelled(self) -> None:
        self._terminal = True
        self.progress.setRange(0, 100)
        self.status_label.setText("Cancelled")
        self.detail_label.setText("Stopped. Ollama can resume this download later.")
        self.percent_label.setText("—")
        self.cancel_button.hide()


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
        self.catalog_worker: OllamaCatalogWorker | None = None
        self.tag_workers: dict[str, OllamaModelTagsWorker] = {}
        self.catalog: list[dict[str, Any]] = []
        self.tags_cache: dict[str, list[dict[str, Any]]] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(30, 24, 24, 22)
        root.setSpacing(16)

        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(14)
        root.addWidget(workspace, 1)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("Models")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Browse the official Ollama library, choose an exact variant and manage local models.")
        subtitle.setObjectName("PageSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setIcon(app_icon("mdi6.refresh", "#B7BEC9"))
        self.refresh_button.clicked.connect(self.refresh_all)
        header.addWidget(self.refresh_button)
        workspace_layout.addLayout(header)

        self.tabs = QTabWidget()
        workspace_layout.addWidget(self.tabs, 1)
        self.discover_tab = QWidget()
        self.library_tab = QWidget()
        self.tabs.addTab(self.discover_tab, app_icon("mdi6.compass-outline"), "Discover")
        self.tabs.addTab(self.library_tab, app_icon("mdi6.database-outline"), "My models")
        self.tabs.tabBar().setIconSize(QSize(16, 16))
        self._build_discover()
        self._build_library()

        self._build_downloads_panel(root)
        QTimer.singleShot(400, self.load_catalog)

    def _build_discover(self) -> None:
        layout = QVBoxLayout(self.discover_tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        self.catalog_status = QLabel("Loading the official Ollama model catalog…")
        self.catalog_status.setObjectName("Muted")
        layout.addWidget(self.catalog_status)

        self.catalog_search = QLineEdit()
        self.catalog_search.setPlaceholderText("Search models by name or description…")
        self.catalog_search.setClearButtonEnabled(True)
        self.catalog_search.addAction(app_icon("mdi6.magnify", "#9299A6"), QLineEdit.ActionPosition.LeadingPosition)
        self.catalog_search.textChanged.connect(self._filter_catalog)
        layout.addWidget(self.catalog_search)

        browser = QHBoxLayout()
        browser.setSpacing(10)
        self.model_list = QListWidget()
        self.model_list.setObjectName("ModelCatalogList")
        self.model_list.setMinimumWidth(210)
        self.model_list.setMaximumWidth(310)
        self.model_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.model_list.currentItemChanged.connect(self._family_selected)
        browser.addWidget(self.model_list)

        self.variant_panel = QFrame()
        self.variant_panel.setObjectName("SettingCard")
        variant_layout = QVBoxLayout(self.variant_panel)
        variant_layout.setContentsMargins(16, 15, 16, 15)
        variant_layout.setSpacing(10)
        self.selected_model_title = QLabel("Select a model")
        self.selected_model_title.setObjectName("CardTitle")
        self.selected_model_title.setWordWrap(True)
        self.selected_model_summary = QLabel("Choose a model family on the left to inspect its available sizes and variants.")
        self.selected_model_summary.setObjectName("CardDescription")
        self.selected_model_summary.setWordWrap(True)
        self.selected_model_summary.setMinimumHeight(65)
        self.tag_count_label = QLabel("")
        self.tag_count_label.setObjectName("Muted")
        self.variant_label = QLabel("Exact model variant")
        self.variant_label.setObjectName("SectionTitle")
        self.variant_combo = QComboBox()
        self.variant_combo.setMinimumHeight(42)
        self.variant_combo.setEnabled(False)
        self.variant_combo.currentIndexChanged.connect(self._variant_selected)
        self.variant_details = QLabel("Select a model to load its available tags from Ollama.")
        self.variant_details.setObjectName("Muted")
        self.variant_details.setWordWrap(True)
        self.download_selected_button = QPushButton("Download selected variant")
        self.download_selected_button.setObjectName("PrimaryButton")
        self.download_selected_button.setIcon(app_icon("mdi6.download", "#FFFFFF"))
        self.download_selected_button.clicked.connect(self._download_selected_variant)
        self.download_selected_button.setEnabled(False)
        variant_layout.addWidget(self.selected_model_title)
        variant_layout.addWidget(self.selected_model_summary)
        variant_layout.addWidget(self.tag_count_label)
        variant_layout.addSpacing(8)
        variant_layout.addWidget(self.variant_label)
        variant_layout.addWidget(self.variant_combo)
        variant_layout.addWidget(self.variant_details, 1)
        variant_layout.addWidget(self.download_selected_button)
        browser.addWidget(self.variant_panel, 1)
        layout.addLayout(browser, 1)

        manual_frame = QFrame()
        manual_frame.setObjectName("Surface")
        manual_layout = QHBoxLayout(manual_frame)
        manual_layout.setContentsMargins(12, 10, 12, 10)
        self.custom_model_input = QLineEdit()
        self.custom_model_input.setPlaceholderText("Or enter an exact Ollama tag, e.g. qwen3:8b-q4_K_M")
        self.custom_model_input.returnPressed.connect(self._pull_custom)
        self.custom_pull_button = QPushButton("Download tag")
        self.custom_pull_button.setIcon(app_icon("mdi6.download", "#FFFFFF"))
        self.custom_pull_button.setObjectName("GhostButton")
        self.custom_pull_button.clicked.connect(self._pull_custom)
        manual_layout.addWidget(self.custom_model_input, 1)
        manual_layout.addWidget(self.custom_pull_button)
        layout.addWidget(manual_frame)

    def _build_library(self) -> None:
        layout = QVBoxLayout(self.library_tab)
        layout.setContentsMargins(8, 12, 8, 8)
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

    def _build_downloads_panel(self, root: QHBoxLayout) -> None:
        self.downloads_frame = QFrame()
        self.downloads_frame.setObjectName("DownloadSidebar")
        self.downloads_frame.setMinimumWidth(264)
        self.downloads_frame.setMaximumWidth(304)
        downloads_layout = QVBoxLayout(self.downloads_frame)
        downloads_layout.setContentsMargins(14, 15, 14, 14)
        downloads_layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("Downloads")
        title.setObjectName("SectionTitle")
        self.active_count = QLabel("No active downloads")
        self.active_count.setObjectName("Muted")
        self.active_count.setWordWrap(True)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.active_count)
        downloads_layout.addLayout(header)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #343A44;")
        downloads_layout.addWidget(separator)
        self.jobs_empty = QLabel("Your downloads will appear here.")
        self.jobs_empty.setObjectName("Muted")
        self.jobs_empty.setWordWrap(True)
        self.jobs_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        downloads_layout.addWidget(self.jobs_empty, 1)
        self.jobs_scroll = QScrollArea()
        self.jobs_scroll.setWidgetResizable(True)
        self.jobs_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.jobs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.jobs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.jobs_container = QWidget()
        self.jobs_layout = QVBoxLayout(self.jobs_container)
        self.jobs_layout.setContentsMargins(0, 0, 4, 0)
        self.jobs_layout.setSpacing(9)
        self.jobs_layout.addStretch(1)
        self.jobs_scroll.setWidget(self.jobs_container)
        downloads_layout.addWidget(self.jobs_scroll, 1)
        root.addWidget(self.downloads_frame)

    def set_endpoint(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def load_catalog(self) -> None:
        if self.catalog_worker and self.catalog_worker.isRunning():
            return
        self.catalog_status.setText("Fetching model families from ollama.com…")
        self.catalog_status.setStyleSheet("")
        worker = OllamaCatalogWorker(self)
        self.catalog_worker = worker
        worker.loaded.connect(self._catalog_loaded)
        worker.failed.connect(self._catalog_failed)
        worker.finished.connect(lambda current=worker: self._catalog_finished(current))
        worker.start()

    def _catalog_loaded(self, models: list[dict]) -> None:
        self.catalog = models
        selected_name = self._selected_family_name()
        self.model_list.blockSignals(True)
        self.model_list.clear()
        for model in models:
            name = str(model.get("name", "")).strip()
            if not name:
                continue
            count = model.get("tag_count")
            text = name if not count else f"{name}   ·   {count} tags"
            item = QListWidgetItem(app_icon("mdi6.cube-outline", "#A8AFBC"), text)
            item.setData(Qt.ItemDataRole.UserRole, model)
            item.setToolTip(str(model.get("summary") or name))
            self.model_list.addItem(item)
            if name == selected_name:
                self.model_list.setCurrentItem(item)
        if self.model_list.currentItem() is None and self.model_list.count():
            self.model_list.setCurrentRow(0)
        self.model_list.blockSignals(False)
        if self.model_list.currentItem():
            self._family_selected(self.model_list.currentItem(), None)
        self.catalog_status.setText(f"Official Ollama catalog · {len(models):,} model families")
        self._filter_catalog(self.catalog_search.text())

    def _catalog_failed(self, message: str) -> None:
        self.catalog_status.setText(f"Could not load Ollama catalog: {message}")
        self.catalog_status.setStyleSheet("color: #E59A9A;")
        self.status_message.emit(f"Could not load ollama.com model catalog: {message}")

    def _catalog_finished(self, worker: OllamaCatalogWorker) -> None:
        if self.catalog_worker is worker:
            self.catalog_worker = None
        worker.deleteLater()

    def _selected_family_name(self) -> str:
        item = self.model_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole).get("name", "")) if item else ""

    def _filter_catalog(self, query: str) -> None:
        needle = query.strip().casefold()
        for row in range(self.model_list.count()):
            item = self.model_list.item(row)
            model = item.data(Qt.ItemDataRole.UserRole) or {}
            haystack = f'{model.get("name", "")} {model.get("summary", "")}'.casefold()
            item.setHidden(bool(needle) and needle not in haystack)

    def _family_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        model = current.data(Qt.ItemDataRole.UserRole) or {}
        name = str(model.get("name", "")).strip()
        self.selected_model_title.setText(name)
        self.selected_model_summary.setText(str(model.get("summary") or "No description is available for this model."))
        self.tag_count_label.setText(f'{model.get("tag_count", "Loading")} variants listed by Ollama')
        self.variant_combo.clear()
        self.variant_combo.setEnabled(False)
        self.download_selected_button.setEnabled(False)
        self.variant_details.setText("Loading exact tags, parameter sizes and download sizes…")
        if name in self.tags_cache:
            self._populate_variants(name, self.tags_cache[name])
            return
        if name in self.tag_workers and self.tag_workers[name].isRunning():
            return
        worker = OllamaModelTagsWorker(name, self)
        self.tag_workers[name] = worker
        worker.loaded.connect(self._tags_loaded)
        worker.failed.connect(self._tags_failed)
        worker.finished.connect(lambda current_worker=worker, key=name: self._tags_finished(key, current_worker))
        worker.start()

    def _tags_loaded(self, model_name: str, tags: list[dict]) -> None:
        self.tags_cache[model_name] = tags
        if self._selected_family_name() == model_name:
            self._populate_variants(model_name, tags)

    def _tags_failed(self, model_name: str, message: str) -> None:
        if self._selected_family_name() == model_name:
            self.variant_details.setText(f"Could not load variants: {message}")
            self.variant_details.setStyleSheet("color: #E59A9A;")
        self.status_message.emit(f"Could not load tags for {model_name}: {message}")

    def _tags_finished(self, name: str, worker: OllamaModelTagsWorker) -> None:
        if self.tag_workers.get(name) is worker:
            self.tag_workers.pop(name, None)
        worker.deleteLater()

    def _populate_variants(self, model_name: str, tags: list[dict]) -> None:
        self.variant_combo.blockSignals(True)
        self.variant_combo.clear()
        for tag in tags:
            self.variant_combo.addItem(_variant_label(model_name, tag), tag)
        self.variant_combo.blockSignals(False)
        if tags:
            latest_index = next((i for i, tag in enumerate(tags) if tag.get("latest")), 0)
            self.variant_combo.setCurrentIndex(latest_index)
            self.variant_combo.setEnabled(True)
            self.download_selected_button.setEnabled(True)
            self.tag_count_label.setText(f"{len(tags)} exact variants available")
            self._variant_selected(latest_index)
        else:
            self.variant_details.setText("Ollama did not return any downloadable tags for this model.")
            self.download_selected_button.setEnabled(False)

    def _variant_selected(self, _index: int = -1) -> None:
        item = self.variant_combo.currentData()
        if not isinstance(item, dict):
            self.variant_details.setText("Choose a model variant.")
            self.download_selected_button.setEnabled(False)
            return
        details = [
            f'Exact pull name: {item.get("reference", "")}',
            f'Download size: {item.get("size") or "Not listed"}',
            f'Context window: {item.get("context") or "Not listed"}',
            f'Input: {item.get("input") or "Not listed"}',
            f'Updated: {item.get("updated") or "Not listed"}',
        ]
        self.variant_details.setText("\n".join(details))
        self.variant_details.setStyleSheet("")
        self.download_selected_button.setEnabled(True)

    def _download_selected_variant(self) -> None:
        item = self.variant_combo.currentData()
        if isinstance(item, dict):
            reference = str(item.get("reference") or "")
            if reference:
                self.start_download(reference)

    def _pull_custom(self) -> None:
        model = self.custom_model_input.text().strip()
        if model:
            self.start_download(model)
            self.custom_model_input.clear()

    def start_download(self, model_name: str) -> None:
        model_name = model_name.strip()
        if not model_name:
            return
        existing_worker = self.workers.get(model_name)
        if existing_worker and existing_worker.isRunning():
            self.status_message.emit(f"A download for {model_name} is already in progress.")
            return
        if any((item.get("name") or item.get("model")) == model_name for item in self.models):
            self.status_message.emit(f"{model_name} is already installed.")
            self.tabs.setCurrentWidget(self.library_tab)
            return
        old_card = self.jobs.get(model_name)
        if old_card:
            self.jobs_layout.removeWidget(old_card)
            old_card.deleteLater()
        card = DownloadJobCard(model_name)
        card.cancel_requested.connect(self._cancel_download)
        self.jobs[model_name] = card
        self.jobs_layout.insertWidget(max(0, self.jobs_layout.count() - 1), card)
        worker = PullWorker(self.endpoint, model_name, self)
        self.workers[model_name] = worker
        worker.progress.connect(lambda event, name=model_name: self._on_progress(name, event))
        worker.completed.connect(lambda name: self._on_download_completed(name))
        worker.failed.connect(lambda error, name=model_name: self._on_download_failed(name, error))
        worker.cancelled.connect(lambda name: self._on_download_cancelled(name))
        worker.finished.connect(lambda name=model_name: self._cleanup_worker(name))
        self._update_jobs_panel()
        self.jobs_scroll.verticalScrollBar().setValue(self.jobs_scroll.verticalScrollBar().maximum())
        worker.start()
        self.status_message.emit(f"Started downloading {model_name}.")

    def _cancel_download(self, model_name: str) -> None:
        worker = self.workers.get(model_name)
        card = self.jobs.get(model_name)
        if worker is None or not worker.isRunning() or card is None:
            return
        card.request_cancel()
        worker.cancel()
        self.status_message.emit(f"Cancelling {model_name}…")

    def _on_progress(self, model_name: str, event: dict) -> None:
        card = self.jobs.get(model_name)
        if card:
            card.update_event(event)

    def _on_download_completed(self, model_name: str) -> None:
        card = self.jobs.get(model_name)
        if card:
            card.finish(True)
        self.status_message.emit(f"{model_name} is ready to use.")
        self.refresh_models()

    def _on_download_cancelled(self, model_name: str) -> None:
        card = self.jobs.get(model_name)
        if card:
            card.finish_cancelled()
        self.status_message.emit(f"Download cancelled: {model_name}. Ollama may resume it if you download it again.")

    def _on_download_failed(self, model_name: str, error: str) -> None:
        card = self.jobs.get(model_name)
        if card:
            card.finish(False, error)
        self.status_message.emit(f"Download failed for {model_name}: {error}")

    def _cleanup_worker(self, model_name: str) -> None:
        worker = self.workers.pop(model_name, None)
        if worker:
            worker.deleteLater()
        self._update_jobs_panel()

    def _update_jobs_panel(self) -> None:
        active = sum(worker.isRunning() for worker in self.workers.values())
        self.active_count.setText(f"{active} active" if active else "No active downloads")
        count = len(self.jobs)
        self.jobs_empty.setVisible(count == 0)
        self.jobs_scroll.setVisible(count > 0)
        self.jobs_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded if count > 1 else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        for card in self.jobs.values():
            card.set_compact(count > 1)

    def refresh_all(self) -> None:
        self.refresh_models()
        self.load_catalog()

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
            remove.setIcon(app_icon("mdi6.trash-can-outline", "#F09BA4"))
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
