from __future__ import annotations

from datetime import datetime, timezone
import uuid

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QAbstractAnimation, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QTextBrowser,
    QVBoxLayout, QWidget,
)

from core.attachments import AttachmentError, prepare_attachment
from core.chat_history import ChatHistoryStore

from core.secrets import SecretStoreError
from core.settings import SettingsStore
from core.speech.whisper_manager import WhisperModelManager
from ui.audio_recorder import AudioRecorder
from ui.mic_button import CircularMicButton
from ui.workers import (
    ChatWorker, ModelCapabilitiesWorker, WhisperDownloadWorker, WhisperTranscriptionWorker,
)
from ui.theme import app_icon


class PromptComposer(QPlainTextEdit):
    send_requested = Signal()
    files_dropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.send_requested.emit()
            return
        super().keyPressEvent(event)


class ThinkingIndicator(QWidget):
    """Three softly pulsing dots shown while a response is being generated."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._animations: list[QPropertyAnimation] = []
        for index in range(3):
            dot = QLabel("●", self)
            dot.setObjectName("ThinkingDot")
            effect = QGraphicsOpacityEffect(dot)
            effect.setOpacity(0.22)
            dot.setGraphicsEffect(effect)
            layout.addWidget(dot)
            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.setDuration(900)
            animation.setStartValue(0.22)
            animation.setKeyValueAt(0.5, 1.0)
            animation.setEndValue(0.22)
            animation.setLoopCount(-1)
            animation.setEasingCurve(QEasingCurve.Type.InOutSine)
            self._animations.append(animation)
            animation.start()
            animation.setCurrentTime(index * 210)
        self.hide()

    def set_running(self, running: bool) -> None:
        self.setVisible(running)
        for animation in self._animations:
            if running and animation.state() != QAbstractAnimation.State.Running:
                animation.start()
            elif not running:
                animation.stop()


class ChatPage(QWidget):
    conversations_changed = Signal(list)

    def __init__(self, endpoint: str, temperature: float = 0.7, settings: SettingsStore | None = None,
                 whisper_manager: WhisperModelManager | None = None, parent=None) -> None:
        super().__init__(parent)
        self.endpoint = endpoint
        self.temperature = temperature
        self.settings = settings or SettingsStore()
        self.whisper_manager = whisper_manager or WhisperModelManager(self.settings.speech_models_directory)
        self.history_store = ChatHistoryStore()
        self.conversations: list[dict] = self.history_store.load()
        self.active_conversation: dict | None = None
        self._active_assistant_message: dict | None = None
        self._history_save_timer = QTimer(self)
        self._history_save_timer.setSingleShot(True)
        self._history_save_timer.setInterval(450)
        self._history_save_timer.timeout.connect(self._persist_current_conversation)
        self.api_profiles: list[dict] = []
        self.local_models: list[dict] = []
        self.history: list[dict[str, object]] = []
        self.attachments: list[dict] = []
        self.capabilities_cache: dict[str, dict] = {}
        self.capabilities_workers: dict[str, ModelCapabilitiesWorker] = {}
        self._active_model_supports_vision = False
        self._think_supported = False
        self._think_values: list[object] = []
        self._think_default: object = None
        self._think_mode = "boolean"
        self.worker: ChatWorker | None = None
        self.whisper_download_worker: WhisperDownloadWorker | None = None
        self.transcription_worker: WhisperTranscriptionWorker | None = None
        self.recorder = AudioRecorder(self)
        self._assistant_body: QLabel | None = None
        self._assistant_thinking_header: QPushButton | None = None
        self._assistant_thinking_body: QTextBrowser | None = None
        self._assistant_thinking_indicator: ThinkingIndicator | None = None
        self._streaming_text = ""
        self._thinking_text = ""

        self.recorder.recording_changed.connect(self._on_recording_changed)
        self.recorder.recording_finished.connect(self._on_recording_finished)
        self.recorder.failed.connect(self._on_voice_error)

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 22)
        root.setSpacing(16)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("Chat")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Chat with local models and your connected AI providers.")
        subtitle.setObjectName("PageSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("ModelPicker")
        self.model_combo.setMinimumWidth(175)
        self.model_combo.setMaximumWidth(225)
        self.model_combo.setFixedHeight(36)
        self.model_combo.setMinimumContentsLength(12)
        self.model_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.model_combo.setPlaceholderText("Select model")
        self.model_combo.currentIndexChanged.connect(self._on_model_selection_changed)
        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.transcript = QWidget()
        self.transcript_layout = QVBoxLayout(self.transcript)
        self.transcript_layout.setContentsMargins(0, 8, 12, 18)
        self.transcript_layout.setSpacing(14)
        self.transcript_layout.addStretch(1)
        self.scroll.setWidget(self.transcript)
        root.addWidget(self.scroll, 1)

        self.welcome = QFrame()
        self.welcome.setObjectName("HeroCard")
        welcome_layout = QVBoxLayout(self.welcome)
        welcome_layout.setContentsMargins(25, 22, 25, 22)
        welcome_title = QLabel("What would you like to explore?")
        welcome_title.setObjectName("CardTitle")
        welcome_title.setStyleSheet("font-size: 19px;")
        welcome_copy = QLabel("Choose a model below and start a conversation. You can also dictate a message with local Whisper speech recognition.")
        welcome_copy.setObjectName("CardDescription")
        welcome_copy.setWordWrap(True)
        welcome_layout.addWidget(welcome_title)
        welcome_layout.addWidget(welcome_copy)
        self.transcript_layout.insertWidget(0, self.welcome)

        composer_card = QFrame()
        composer_card.setObjectName("Surface")
        composer_layout = QVBoxLayout(composer_card)
        composer_layout.setContentsMargins(13, 13, 13, 11)
        composer_layout.setSpacing(9)
        self.attachment_scroll = QScrollArea()
        self.attachment_scroll.setObjectName("AttachmentStrip")
        self.attachment_scroll.setWidgetResizable(True)
        self.attachment_scroll.setFixedHeight(62)
        self.attachment_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.attachment_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.attachment_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.attachment_container = QWidget()
        self.attachment_layout = QHBoxLayout(self.attachment_container)
        self.attachment_layout.setContentsMargins(2, 2, 2, 2)
        self.attachment_layout.setSpacing(7)
        self.attachment_scroll.setWidget(self.attachment_container)
        self.attachment_scroll.hide()
        composer_layout.addWidget(self.attachment_scroll)

        self.composer = PromptComposer()
        self.composer.setObjectName("Composer")
        self.composer.setPlaceholderText("Message your model…  (Ctrl + Enter to send, or drop files here)")
        self.composer.setMinimumHeight(88)
        self.composer.setMaximumHeight(170)
        self.composer.send_requested.connect(self.send_message)
        self.composer.files_dropped.connect(self._add_attachment_paths)
        composer_layout.addWidget(self.composer)

        action_row = QHBoxLayout()
        self.attach_button = QPushButton()
        self.attach_button.setIcon(app_icon("mdi6.plus", "#D7DCE6"))
        self.attach_button.setIconSize(QSize(18, 18))
        self.attach_button.setObjectName("AddAttachmentButton")
        self.attach_button.setFixedSize(36, 36)
        self.attach_button.setToolTip("Add images or files")
        self.attach_button.clicked.connect(self._choose_attachments)
        self.think_button = QPushButton("Think")
        self.think_button.setIcon(app_icon("mdi6.brain", "#B7BEC9"))
        self.think_button.setIconSize(QSize(17, 17))
        self.think_button.setObjectName("GhostButton")
        self.think_button.setCheckable(True)
        self.think_button.setEnabled(False)
        self.think_button.setToolTip("Select a local model that supports thinking to enable this.")
        self.think_button.toggled.connect(self._think_toggled)
        self.think_level_combo = QComboBox()
        self.think_level_combo.setMinimumWidth(84)
        self.think_level_combo.setMaximumWidth(100)
        self.think_level_combo.hide()
        self.hint = QLabel("Choose a model to begin.")
        self.hint.setObjectName("Muted")
        self.mic_button = CircularMicButton()
        self.mic_button.clicked.connect(self._toggle_voice_input)
        self.send_button = QPushButton("Send")
        self.send_button.setIcon(app_icon("mdi6.arrow-up", "#FFFFFF"))
        self.send_button.setIconSize(QSize(16, 16))
        self.send_button.setObjectName("PrimaryButton")
        self.send_button.clicked.connect(self.send_message)
        action_row.addWidget(self.attach_button)
        action_row.addWidget(self.model_combo)
        action_row.addWidget(self.think_button)
        action_row.addWidget(self.think_level_combo)
        action_row.addWidget(self.hint, 1)
        action_row.addWidget(self.mic_button)
        action_row.addWidget(self.send_button)
        composer_layout.addLayout(action_row)
        root.addWidget(composer_card)

        if self.conversations:
            latest = max(self.conversations, key=lambda item: str(item.get("updated_at", "")))
            self.open_conversation(str(latest.get("id", "")))
        self._emit_conversations_changed()

    def set_endpoint(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def set_temperature(self, temperature: float) -> None:
        self.temperature = temperature

    def set_speech_settings(self, model_name: str, language: str, models_directory: str) -> None:
        self.whisper_manager.set_models_directory(models_directory)
        self.settings.set("speech_default_model", model_name)
        self.settings.set("speech_language", language)

    def set_remote_profiles(self, profiles: list[dict]) -> None:
        self.api_profiles = [dict(profile) for profile in profiles]
        self._rebuild_model_list()

    def set_models(self, models: list[dict]) -> None:
        self.local_models = list(models)
        self._rebuild_model_list()

    def notify_conversations_changed(self) -> None:
        self._emit_conversations_changed()

    def _rebuild_model_list(self) -> None:
        previous = self.model_combo.currentData()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model in self.local_models:
            name = model.get("name") or model.get("model")
            if name:
                self.model_combo.addItem(app_icon("mdi6.laptop", "#AAB2C0"), f"Ollama  ·  {name}", {"source": "ollama", "model_id": str(name)})
        for profile in self.api_profiles:
            for model in profile.get("models", []):
                model_id = str(model.get("id", "")).strip()
                if model_id:
                    self.model_combo.addItem(
                        app_icon("mdi6.cloud-outline", "#AAB2C0"),
                        f"{profile.get('name', 'API')}  ·  {model.get('name') or model_id}",
                        {"source": "remote", "profile_id": profile["id"], "model_id": model_id},
                    )
        preferred = previous
        if preferred is None and self.active_conversation:
            preferred = self.active_conversation.get("model_selection")
        if preferred is not None:
            for index in range(self.model_combo.count()):
                if self.model_combo.itemData(index) == preferred:
                    self.model_combo.setCurrentIndex(index)
                    break
        self.model_combo.blockSignals(False)
        self.send_button.setEnabled(self.model_combo.count() > 0)
        self._update_model_hint()

    def _on_model_selection_changed(self, _index: int = -1) -> None:
        self._update_model_hint()
        if self.active_conversation and self.model_combo.currentData():
            self.active_conversation["model_selection"] = dict(self.model_combo.currentData())
            self._schedule_history_save()

    def _set_model_features(
        self, vision: bool, think_values: list[object] | None = None, think_default: object = None,
        think_tooltip: str = "",
    ) -> None:
        self._active_model_supports_vision = vision
        self._think_values = list(think_values or [])
        self._think_default = think_default
        self._think_supported = any(value is True for value in self._think_values) or any(
            isinstance(value, str) and value for value in self._think_values
        )
        self.think_button.blockSignals(True)
        self.think_button.setChecked(False)
        self.think_button.setText("Think")
        self.think_button.blockSignals(False)
        self.think_level_combo.blockSignals(True)
        self.think_level_combo.clear()
        string_levels = [value for value in self._think_values if isinstance(value, str)]
        self._think_mode = "levels" if string_levels else "boolean"
        for level in string_levels:
            self.think_level_combo.addItem(str(level).capitalize(), level)
        default_index = self.think_level_combo.findData(think_default)
        if default_index >= 0:
            self.think_level_combo.setCurrentIndex(default_index)
        self.think_level_combo.blockSignals(False)
        self.think_level_combo.setVisible(self._think_supported and bool(string_levels))
        self.think_button.setEnabled(self._think_supported)
        self.think_button.setToolTip(
            think_tooltip or (
                "Enable model reasoning output." if self._think_supported
                else "This model does not advertise a Think capability."
            )
        )
        if vision:
            self.attach_button.setToolTip("Attach images and documents. Drop files into the message box.")
        else:
            self.attach_button.setToolTip("Attach documents. Image input requires a vision-capable model.")

    def _remote_model_supports_vision(self, profile: dict, model_id: str) -> bool:
        provider = str(profile.get("provider", "openai_compatible")).lower()
        model = model_id.lower().split("/")[-1]
        if provider == "google":
            return model.startswith("gemini-")
        if provider == "anthropic":
            return "claude-" in model
        known_prefixes = ("gpt-4o", "gpt-4.1", "gpt-4.5", "gpt-5", "o1", "o3", "o4")
        if provider == "openai":
            return model.startswith(known_prefixes)
        return any(token in model for token in (
            "gpt-4o", "gpt-4.1", "gpt-5", "claude-3", "claude-4", "gemini-",
            "llava", "qwen-vl", "qwen2.5-vl", "qwen2-vl", "pixtral",
            "internvl", "minicpm-v", "moondream", "molmo", "phi-3-vision",
        ))

    def _load_model_capabilities(self, model_name: str) -> None:
        if model_name in self.capabilities_cache or model_name in self.capabilities_workers:
            return
        worker = ModelCapabilitiesWorker(self.endpoint, model_name, self)
        self.capabilities_workers[model_name] = worker
        worker.loaded.connect(self._capabilities_loaded)
        worker.failed.connect(self._capabilities_failed)
        worker.finished.connect(lambda current=worker, name=model_name: self._capabilities_finished(name, current))
        worker.start()

    def _capabilities_loaded(self, model_name: str, details: dict) -> None:
        self.capabilities_cache[model_name] = details
        selection = self.model_combo.currentData()
        if selection and selection.get("source") == "ollama" and selection.get("model_id") == model_name:
            capabilities = {str(item).lower() for item in details.get("capabilities", [])}
            vision = "vision" in capabilities
            thinking = details.get("thinking") or {}
            values = thinking.get("values", []) if isinstance(thinking, dict) else []
            if not values and "thinking" in capabilities:
                values = [True]
            self._set_model_features(vision, values, thinking.get("default") if isinstance(thinking, dict) else None)
            if self.attachments and not vision and any(item.get("kind") == "image" for item in self.attachments):
                self.hint.setText("The selected model cannot process images. Choose a vision-capable model.")
            else:
                self.hint.setText(f"Local Ollama model · {model_name}")

    def _capabilities_failed(self, model_name: str, message: str) -> None:
        selection = self.model_combo.currentData()
        if selection and selection.get("source") == "ollama" and selection.get("model_id") == model_name:
            self._set_model_features(False, [], None, "Could not read this model's capabilities from Ollama.")
            self.hint.setText(f"Could not inspect model capabilities: {message}")

    def _capabilities_finished(self, model_name: str, worker: ModelCapabilitiesWorker) -> None:
        if self.capabilities_workers.get(model_name) is worker:
            self.capabilities_workers.pop(model_name, None)
        worker.deleteLater()

    def _update_model_hint(self, _index: int = -1) -> None:
        selection = self.model_combo.currentData()
        if not selection:
            self._set_model_features(False, [], None, "Select a model first.")
            self.hint.setText("No models available — add a provider in Settings or download a local model.")
            return
        if selection.get("source") == "remote":
            profile = next((item for item in self.api_profiles if item.get("id") == selection.get("profile_id")), {})
            vision = self._remote_model_supports_vision(profile, selection.get("model_id", ""))
            self._set_model_features(
                vision, [], None,
                "Think is currently available for local Ollama models whose /api/show metadata advertises it.",
            )
            suffix = "Image input detected" if vision else "Vision support not detected for this model"
            self.hint.setText(
                f'Cloud API · {profile.get("name", "Connected provider")} · {suffix} · Usage may incur provider charges'
            )
            return
        model_name = str(selection.get("model_id", ""))
        self._set_model_features(False, [], None, "Checking this model's vision and Think capabilities…")
        self.hint.setText(f"Checking capabilities for {model_name}…")
        if model_name in self.capabilities_cache:
            details = self.capabilities_cache[model_name]
            capabilities = {str(item).lower() for item in details.get("capabilities", [])}
            thinking = details.get("thinking") or {}
            values = thinking.get("values", []) if isinstance(thinking, dict) else []
            if not values and "thinking" in capabilities:
                values = [True]
            self._set_model_features(
                "vision" in capabilities, values,
                thinking.get("default") if isinstance(thinking, dict) else None,
            )
            self.hint.setText(f"Local Ollama model · {model_name}")
        else:
            self._load_model_capabilities(model_name)

    def _add_message(
        self, role: str, text: str, streaming: bool = False,
        attachments: list[dict] | None = None,
    ) -> QLabel:
        card = QFrame()
        card.setObjectName("UserMessage" if role == "user" else "AssistantMessage")
        card.setMaximumWidth(920)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 13)
        layout.setSpacing(7)
        label = QLabel("You" if role == "user" else "Assistant")
        label.setObjectName("Muted")
        label.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #D9E8FA;"
            if role == "user" else "font-size: 11px; font-weight: 700; color: #9CA3AF;"
        )
        body = QLabel(text or ("Generating…" if streaming else ""))
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setMinimumHeight(22)
        body.setStyleSheet(
            "font-size: 13px; line-height: 1.5; color: #FFFFFF;"
            if role == "user" else "font-size: 13px; line-height: 1.5; color: #E8EAF0;"
        )
        layout.addWidget(label)
        if attachments:
            attachment_row = QHBoxLayout()
            for attachment in attachments:
                chip = QLabel(
                    f'{attachment.get("name", "Attachment")}  ·  {attachment.get("kind", "file").upper()}'
                )
                chip.setObjectName("AttachmentMessageChip")
                attachment_row.addWidget(chip)
            attachment_row.addStretch()
            layout.addLayout(attachment_row)
        if role == "assistant":
            thinking_row = QHBoxLayout()
            thinking_header = QPushButton("Thinking process")
            thinking_header.setIcon(app_icon("mdi6.brain", "#AFA4E8"))
            thinking_header.setObjectName("ThinkingHeader")
            thinking_header.setCheckable(True)
            thinking_header.setChecked(False)
            thinking_header.setVisible(False)
            thinking_body = QTextBrowser()
            thinking_body.setObjectName("ThinkingBody")
            thinking_body.setReadOnly(True)
            thinking_body.setOpenExternalLinks(False)
            thinking_body.setMaximumHeight(250)
            thinking_body.setVisible(False)
            thinking_header.toggled.connect(thinking_body.setVisible)
            indicator = ThinkingIndicator(card)
            indicator.set_running(streaming)
            thinking_row.addWidget(thinking_header)
            thinking_row.addWidget(indicator)
            thinking_row.addStretch(1)
            layout.addLayout(thinking_row)
            layout.addWidget(thinking_body)
            self._assistant_thinking_header = thinking_header
            self._assistant_thinking_body = thinking_body
            self._assistant_thinking_indicator = indicator
        layout.addWidget(body)
        alignment = Qt.AlignmentFlag.AlignRight if role == "user" else Qt.AlignmentFlag.AlignLeft
        self.transcript_layout.insertWidget(self.transcript_layout.count() - 1, card, alignment=alignment)
        self.welcome.hide()
        QTimer.singleShot(0, self._scroll_to_bottom)
        return body

    def _scroll_to_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _emit_conversations_changed(self) -> None:
        items = []
        for conversation in sorted(
            self.conversations,
            key=lambda item: str(item.get("updated_at", "")),
            reverse=True,
        ):
            items.append({
                "id": str(conversation.get("id", "")),
                "title": str(conversation.get("title") or "New chat"),
                "updated_at": str(conversation.get("updated_at", "")),
                "active": bool(
                    self.active_conversation
                    and conversation.get("id") == self.active_conversation.get("id")
                ),
            })
        self.conversations_changed.emit(items)

    def _ensure_conversation(self, title: str, selection: dict) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if self.active_conversation is None:
            self.active_conversation = {
                "id": uuid.uuid4().hex,
                "title": (title.strip().splitlines()[0][:52] if title.strip() else "New chat"),
                "created_at": now,
                "updated_at": now,
                "model_selection": dict(selection),
                "messages": self.history,
            }
            self.conversations.append(self.active_conversation)
        else:
            if len(self.history) <= 1:
                self.active_conversation["title"] = (
                    title.strip().splitlines()[0][:52] if title.strip() else "New chat"
                )
            self.active_conversation["model_selection"] = dict(selection)
            self.active_conversation["messages"] = self.history

    def _schedule_history_save(self) -> None:
        if self.active_conversation is not None:
            self._history_save_timer.start()

    def _persist_current_conversation(self) -> None:
        if self.active_conversation is None or not self.history:
            self._emit_conversations_changed()
            return
        self.active_conversation["messages"] = self.history
        self.active_conversation["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            self.history_store.save(self.conversations)
        except (OSError, TypeError, ValueError) as exc:
            self.hint.setText(f"Could not save chat history: {exc}")
        self._emit_conversations_changed()

    def save_current_conversation(self) -> None:
        """Flush pending streaming updates before the application closes."""
        self._history_save_timer.stop()
        self._persist_current_conversation()

    @staticmethod
    def _messages_for_model(messages: list[dict[str, object]]) -> list[dict[str, object]]:
        """Keep private UI metadata out of model context while preserving image inputs."""
        model_messages = []
        for message in messages:
            clean = {
                key: message[key]
                for key in ("role", "content", "images")
                if key in message
            }
            if clean:
                model_messages.append(clean)
        return model_messages

    def _clear_transcript(self) -> None:
        while self.transcript_layout.count():
            item = self.transcript_layout.takeAt(0)
            widget = item.widget()
            if widget and widget is not self.welcome:
                widget.deleteLater()
        self.transcript_layout.addStretch(1)
        self._assistant_body = None
        self._assistant_thinking_header = None
        self._assistant_thinking_body = None
        self._assistant_thinking_indicator = None
        self._active_assistant_message = None

    def _render_conversation(self) -> None:
        self._clear_transcript()
        if not self.history:
            self.transcript_layout.insertWidget(0, self.welcome)
            self.welcome.show()
            return
        self.welcome.hide()
        for message in self.history:
            role = str(message.get("role", "assistant"))
            if role not in {"user", "assistant"}:
                continue
            attachments = message.get("attachments")
            if not isinstance(attachments, list):
                attachments = []
            if role == "user" and not attachments:
                attachments = [
                    {"name": image.get("name", "Image"), "kind": "image"}
                    for image in message.get("images", [])
                    if isinstance(image, dict)
                ]
            body = self._add_message(
                role,
                str(message.get("content", "")),
                attachments=attachments,
            )
            if role == "assistant":
                thinking = str(message.get("thinking", ""))
                if thinking and self._assistant_thinking_header and self._assistant_thinking_body:
                    self._assistant_thinking_body.setPlainText(thinking)
                    self._assistant_thinking_header.setVisible(True)
                    self._assistant_thinking_header.setChecked(False)
                if message.get("error") and not message.get("content"):
                    body.setText(f'Unable to generate a response: {message["error"]}')
        QTimer.singleShot(0, self._scroll_to_bottom)

    def open_conversation(self, conversation_id: str) -> bool:
        if self.worker and self.worker.isRunning():
            return False
        conversation = next(
            (item for item in self.conversations if item.get("id") == conversation_id),
            None,
        )
        if conversation is None:
            return False
        self._history_save_timer.stop()
        self.active_conversation = conversation
        messages = conversation.get("messages", [])
        self.history = messages if isinstance(messages, list) else []
        preferred = conversation.get("model_selection")
        if isinstance(preferred, dict):
            self.model_combo.blockSignals(True)
            for index in range(self.model_combo.count()):
                if self.model_combo.itemData(index) == preferred:
                    self.model_combo.setCurrentIndex(index)
                    break
            self.model_combo.blockSignals(False)
        self.attachments.clear()
        self._render_attachments()
        self._render_conversation()
        self._update_model_hint()
        self.hint.setText(f'Saved conversation · {len(self.history)} messages')
        self._emit_conversations_changed()
        return True

    def new_chat(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.save_current_conversation()
        self.active_conversation = None
        self.history = []
        self.attachments.clear()
        self._streaming_text = ""
        self._thinking_text = ""
        self._active_assistant_message = None
        self._render_attachments()
        self._render_conversation()
        self._emit_conversations_changed()

    def _toggle_voice_input(self) -> None:
        if self.transcription_worker and self.transcription_worker.isRunning():
            return
        if self.whisper_download_worker and self.whisper_download_worker.isRunning():
            return
        if self.recorder.is_recording:
            self.recorder.stop_recording()
            return
        model_name = self.settings.speech_default_model
        if self.whisper_manager.is_installed(model_name):
            self._start_recording()
            return
        answer = QMessageBox.question(
            self, "Download Whisper model",
            f"Whisper {model_name} is not installed yet.\n\nDownload this free multilingual model now? The download will be saved to your Voice models folder.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._download_whisper_model(model_name)

    def _download_whisper_model(self, model_name: str) -> None:
        self.mic_button.setEnabled(False)
        self.mic_button.set_download_progress(0)
        self.hint.setText(f"Downloading Whisper {model_name}…")
        worker = WhisperDownloadWorker(self.whisper_manager, model_name, self)
        self.whisper_download_worker = worker
        worker.progress.connect(self._on_whisper_download_progress)
        worker.completed.connect(lambda _path: self._on_whisper_downloaded(model_name))
        worker.failed.connect(self._on_whisper_download_failed)
        worker.finished.connect(lambda current=worker: self._whisper_download_finished(current))
        worker.start()

    def _on_whisper_download_progress(self, current: int, total: int) -> None:
        percent = int(current * 100 / total) if total > 0 else 0
        self.mic_button.set_download_progress(percent)
        self.hint.setText(f"Downloading Whisper… {percent}%")

    def _on_whisper_downloaded(self, model_name: str) -> None:
        self.mic_button.set_download_progress(None)
        self.hint.setText(f"Whisper {model_name} is ready. Starting microphone…")
        self._start_recording()

    def _on_whisper_download_failed(self, message: str) -> None:
        self.mic_button.set_download_progress(None)
        self.mic_button.setEnabled(True)
        self.hint.setText(f"Whisper download failed: {message}")

    def _whisper_download_finished(self, worker: WhisperDownloadWorker) -> None:
        if self.whisper_download_worker is worker:
            self.whisper_download_worker = None
        worker.deleteLater()

    def _start_recording(self) -> None:
        self.recorder.start_recording()

    def _on_recording_changed(self, recording: bool) -> None:
        self.mic_button.set_recording(recording)
        self.mic_button.setEnabled(True)
        if recording:
            self.hint.setText("Listening… select the microphone again to finish")
            self.send_button.setEnabled(False)
        else:
            self.send_button.setEnabled(self.model_combo.count() > 0)

    def _on_voice_error(self, message: str) -> None:
        self.hint.setText(message)
        self.mic_button.set_download_progress(None)
        self.mic_button.set_recording(False)
        self.mic_button.setEnabled(True)
        self.send_button.setEnabled(self.model_combo.count() > 0)

    def _on_recording_finished(self, audio_path: str) -> None:
        model_name = self.settings.speech_default_model
        language = self.settings.speech_language
        self.hint.setText(f"Transcribing with local Whisper {model_name}…")
        self.mic_button.setEnabled(False)
        worker = WhisperTranscriptionWorker(
            self.whisper_manager, audio_path, model_name,
            language=None if language == "auto" else language,
            parent=self,
        )
        self.transcription_worker = worker
        worker.completed.connect(self._on_voice_transcribed)
        worker.failed.connect(self._on_voice_error)
        worker.finished.connect(lambda current=worker: self._transcription_finished(current))
        worker.start()

    def _on_voice_transcribed(self, text: str, language: str) -> None:
        existing = self.composer.toPlainText().strip()
        self.composer.setPlainText(f"{existing}\n{text}" if existing else text)
        self.composer.setFocus()
        self.hint.setText(f"Voice transcribed locally · {language}. Review your text and send when ready.")
        self.mic_button.setEnabled(True)
        self.send_button.setEnabled(self.model_combo.count() > 0)

    def _transcription_finished(self, worker: WhisperTranscriptionWorker) -> None:
        if self.transcription_worker is worker:
            self.transcription_worker = None
        worker.deleteLater()

    def _choose_attachments(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach images or files", "",
            "Supported files (*.png *.jpg *.jpeg *.webp *.gif *.pdf *.docx *.xlsx *.xlsm *.pptx *.txt *.md *.csv *.tsv *.json *.jsonl *.html *.htm *.xml *.yaml *.yml *.py *.js *.ts *.cpp *.h *.sql *.log);;All files (*)",
        )
        if paths:
            self._add_attachment_paths(paths)

    def _add_attachment_paths(self, paths: list[str]) -> None:
        for path in paths:
            if len(self.attachments) >= 8:
                self.hint.setText("You can attach up to 8 files per message.")
                break
            try:
                attachment = prepare_attachment(path)
            except (AttachmentError, OSError, RuntimeError) as exc:
                QMessageBox.warning(self, "Could not attach file", str(exc))
                continue
            total_bytes = sum(int(item.get("size", 0)) for item in self.attachments)
            if total_bytes + int(attachment.get("size", 0)) > 40 * 1024 * 1024:
                QMessageBox.warning(self, "Attachment limit", "The combined attachment size must be 40 MB or less.")
                continue
            if attachment.get("kind") == "image" and not self._active_model_supports_vision:
                QMessageBox.information(
                    self, "Vision is not available",
                    "The selected model is not confirmed to support image input. Choose a vision-capable model, then attach the image again.",
                )
                continue
            if any(item.get("path") == attachment["path"] for item in self.attachments):
                continue
            self.attachments.append(attachment)
        self._render_attachments()

    def _render_attachments(self) -> None:
        while self.attachment_layout.count():
            item = self.attachment_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for index, attachment in enumerate(self.attachments):
            chip = QFrame()
            chip.setObjectName("AttachmentChip")
            chip_layout = QHBoxLayout(chip)
            chip_layout.setContentsMargins(8, 5, 7, 5)
            chip_layout.setSpacing(6)
            icon_name = "mdi6.file-image-outline" if attachment.get("kind") == "image" else "mdi6.file-document-outline"
            icon_label = QLabel()
            icon_label.setPixmap(app_icon(icon_name, "#B9B1E7").pixmap(QSize(18, 18)))
            name = QLabel(str(attachment.get("name", "Attachment")))
            name.setObjectName("AttachmentChipName")
            name.setMaximumWidth(150)
            name.setToolTip(str(attachment.get("name", "")))
            remove = QPushButton()
            remove.setIcon(app_icon("mdi6.close", "#AAB1BE"))
            remove.setObjectName("AttachmentRemoveButton")
            remove.setFixedSize(22, 22)
            remove.clicked.connect(lambda _checked=False, item_index=index: self._remove_attachment(item_index))
            chip_layout.addWidget(icon_label)
            chip_layout.addWidget(name)
            chip_layout.addWidget(remove)
            self.attachment_layout.addWidget(chip)
        self.attachment_layout.addStretch(1)
        self.attachment_scroll.setVisible(bool(self.attachments))

    def _remove_attachment(self, index: int) -> None:
        if 0 <= index < len(self.attachments):
            self.attachments.pop(index)
            self._render_attachments()

    def _selected_think_value(self) -> bool | str | None:
        if not self._think_supported or not self.think_button.isChecked():
            return None
        if self._think_mode == "levels":
            return self.think_level_combo.currentData() or self._think_default
        return True

    def _think_toggled(self, enabled: bool) -> None:
        self.think_level_combo.setVisible(enabled and self._think_mode == "levels")
        if enabled:
            self.think_button.setText("Think on")
            self.think_button.setToolTip("Model reasoning is enabled for this request.")
        else:
            self.think_button.setText("Think")
            self.think_button.setToolTip("Request the model's thinking output.")

    def send_message(self) -> None:
        prompt = self.composer.toPlainText().strip()
        selection = self.model_combo.currentData()
        if (
            (not prompt and not self.attachments)
            or not selection
            or (self.worker and self.worker.isRunning())
            or self.recorder.is_recording
            or (self.transcription_worker and self.transcription_worker.isRunning())
        ):
            return
        if any(item.get("kind") == "image" for item in self.attachments) and not self._active_model_supports_vision:
            self.hint.setText("The selected model does not support image input. Select a vision-capable model.")
            return
        if not prompt:
            prompt = "Please analyze the attached content."
        image_payloads = [
            {"name": item["name"], "mime_type": item["mime_type"], "data": item["data"]}
            for item in self.attachments if item.get("kind") == "image"
        ]
        for attachment in self.attachments:
            if attachment.get("kind") == "file":
                prompt += f'\n\n[Attached file: {attachment["name"]}]\n{attachment["text"]}\n[End of attached file]'
        attachment_display = [
            {"name": item.get("name", "Attachment"), "kind": item.get("kind", "file")}
            for item in self.attachments
        ]
        remote_profile = None
        api_key = ""
        model_id = selection["model_id"]
        if selection["source"] == "remote":
            remote_profile = next((item for item in self.api_profiles if item.get("id") == selection["profile_id"]), None)
            if not remote_profile:
                self.hint.setText("This API connection no longer exists. Refresh the model list.")
                return
            try:
                api_key = self.settings.get_api_key(remote_profile["id"])
            except SecretStoreError as exc:
                self.hint.setText(str(exc))
                return
            if not api_key and remote_profile.get("provider") != "openai_compatible":
                self.hint.setText("API key missing. Update this connection in Settings.")
                return

        selected_think = self._selected_think_value() if not remote_profile else None
        user_message: dict[str, object] = {
            "role": "user",
            "content": prompt,
            "attachments": attachment_display,
        }
        if image_payloads:
            user_message["images"] = image_payloads
        self.history.append(user_message)
        self._ensure_conversation(prompt, selection)
        self._add_message("user", prompt, attachments=attachment_display)
        model_history = self._messages_for_model(self.history)
        self._active_assistant_message = {"role": "assistant", "content": "", "thinking": ""}
        self.history.append(self._active_assistant_message)
        self._assistant_body = self._add_message("assistant", "", streaming=True)
        self._streaming_text = ""
        self._thinking_text = ""
        self.composer.clear()
        self.attachments.clear()
        self._render_attachments()
        self.composer.setEnabled(False)
        self.send_button.setEnabled(False)
        self.mic_button.setEnabled(False)
        self.attach_button.setEnabled(False)
        self.think_button.setEnabled(False)
        self._persist_current_conversation()
        self.worker = ChatWorker(
            self.endpoint, model_id, model_history, self.temperature,
            remote_profile=remote_profile, api_key=api_key,
            think=selected_think,
        )
        self.worker.chunk.connect(self._on_chunk)
        self.worker.thinking_chunk.connect(self._on_thinking_chunk)
        self.worker.completed.connect(self._on_completed)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _on_thinking_chunk(self, chunk: str) -> None:
        self._thinking_text += chunk
        if self._assistant_thinking_body:
            self._assistant_thinking_body.setPlainText(self._thinking_text)
        if self._assistant_thinking_header:
            self._assistant_thinking_header.setVisible(True)
        if self._active_assistant_message is not None:
            self._active_assistant_message["thinking"] = self._thinking_text
        self._schedule_history_save()
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_chunk(self, chunk: str) -> None:
        self._streaming_text += chunk
        if self._assistant_body:
            self._assistant_body.setText(self._streaming_text)
        if self._active_assistant_message is not None:
            self._active_assistant_message["content"] = self._streaming_text
        self._schedule_history_save()
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_completed(self, _metadata: dict) -> None:
        if self._active_assistant_message is not None:
            self._active_assistant_message["content"] = self._streaming_text
            self._active_assistant_message["thinking"] = self._thinking_text
        if self._assistant_body and not self._streaming_text:
            self._assistant_body.setText("The model returned an empty response.")
        if self._assistant_thinking_indicator:
            self._assistant_thinking_indicator.set_running(False)
        if self._assistant_thinking_header:
            self._assistant_thinking_header.setVisible(bool(self._thinking_text))
        self.save_current_conversation()

    def _on_failed(self, message: str) -> None:
        if self._assistant_body:
            self._assistant_body.setText(f"Unable to generate a response: {message}")
        if self._active_assistant_message is not None:
            self._active_assistant_message["content"] = self._streaming_text
            self._active_assistant_message["thinking"] = self._thinking_text
            self._active_assistant_message["error"] = message
        if self._assistant_thinking_indicator:
            self._assistant_thinking_indicator.set_running(False)
        if self._assistant_thinking_header:
            self._assistant_thinking_header.setVisible(bool(self._thinking_text))
        self.save_current_conversation()

    def _worker_finished(self) -> None:
        if self._assistant_thinking_indicator:
            self._assistant_thinking_indicator.set_running(False)
        self.composer.setEnabled(True)
        self.mic_button.setEnabled(True)
        self.send_button.setEnabled(self.model_combo.count() > 0)
        self.attach_button.setEnabled(True)
        self.think_button.setEnabled(self._think_supported)
        self.composer.setFocus()
        self.save_current_conversation()
        self.worker = None

    def insert_voice_text(self, text: str) -> None:
        existing = self.composer.toPlainText().strip()
        self.composer.setPlainText(f"{existing}\n{text}" if existing else text)
        self.composer.setFocus()
