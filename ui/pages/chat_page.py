from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ui.workers import ChatWorker


class PromptComposer(QPlainTextEdit):
    send_requested = Signal()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.send_requested.emit()
            return
        super().keyPressEvent(event)


class ChatPage(QWidget):
    def __init__(self, endpoint: str, temperature: float = 0.7, parent=None) -> None:
        super().__init__(parent)
        self.endpoint = endpoint
        self.temperature = temperature
        self.history: list[dict[str, str]] = []
        self.worker: ChatWorker | None = None
        self._assistant_body: QLabel | None = None
        self._streaming_text = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 27, 34, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("Chat")
        title.setObjectName("PageTitle")
        subtitle = QLabel("A private workspace for conversations with your local models.")
        subtitle.setObjectName("PageSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(210)
        self.model_combo.setPlaceholderText("Select a model")
        self.new_chat_button = QPushButton("＋  New chat")
        self.new_chat_button.setObjectName("GhostButton")
        self.new_chat_button.clicked.connect(self.new_chat)
        header.addWidget(self.model_combo)
        header.addWidget(self.new_chat_button)
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
        welcome_title = QLabel("Your local AI workspace")
        welcome_title.setObjectName("CardTitle")
        welcome_title.setStyleSheet("font-size: 19px;")
        welcome_copy = QLabel(
            "Choose a downloaded model and start a conversation. Your prompts are sent to your configured Ollama server."
        )
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
        self.composer = PromptComposer()
        self.composer.setObjectName("Composer")
        self.composer.setPlaceholderText("Message your local model…  (Ctrl + Enter to send)")
        self.composer.setMinimumHeight(94)
        self.composer.setMaximumHeight(180)
        self.composer.send_requested.connect(self.send_message)
        composer_layout.addWidget(self.composer)

        action_row = QHBoxLayout()
        self.hint = QLabel("Local inference  ·  Conversation stays on your Ollama server")
        self.hint.setObjectName("Muted")
        self.send_button = QPushButton("Send  ↑")
        self.send_button.setObjectName("PrimaryButton")
        self.send_button.clicked.connect(self.send_message)
        action_row.addWidget(self.hint)
        action_row.addStretch()
        action_row.addWidget(self.send_button)
        composer_layout.addLayout(action_row)
        root.addWidget(composer_card)

    def set_endpoint(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def set_temperature(self, temperature: float) -> None:
        self.temperature = temperature

    def set_models(self, models: list[dict]) -> None:
        current = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model in models:
            name = model.get("name") or model.get("model")
            if name:
                self.model_combo.addItem(str(name))
        index = self.model_combo.findText(current)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)
        self.send_button.setEnabled(bool(models))
        self.hint.setText(
            "Local inference  ·  Conversation stays on your Ollama server"
            if models else "No local models yet — open Models to download one."
        )

    def _add_message(self, role: str, text: str, streaming: bool = False) -> QLabel:
        card = QFrame()
        card.setObjectName("UserMessage" if role == "user" else "AssistantMessage")
        card.setMaximumWidth(920)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 13)
        layout.setSpacing(6)
        label = QLabel("You" if role == "user" else "Ollama")
        label.setObjectName("Muted")
        label.setStyleSheet("font-size: 11px; font-weight: 700; color: #a9a1db;" if role == "user" else "font-size: 11px; font-weight: 700;")
        body = QLabel(text or ("Thinking…" if streaming else ""))
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setMinimumHeight(22)
        body.setStyleSheet("font-size: 13px; line-height: 1.5; color: #eceef5;")
        layout.addWidget(label)
        layout.addWidget(body)
        self.transcript_layout.insertWidget(self.transcript_layout.count() - 1, card, alignment=Qt.AlignmentFlag.AlignRight if role == "user" else Qt.AlignmentFlag.AlignLeft)
        self.welcome.hide()
        QTimer.singleShot(0, self._scroll_to_bottom)
        return body

    def _scroll_to_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def new_chat(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.history.clear()
        while self.transcript_layout.count() > 1:
            item = self.transcript_layout.takeAt(0)
            widget = item.widget()
            if widget and widget is not self.welcome:
                widget.deleteLater()
        self.transcript_layout.insertWidget(0, self.welcome)
        self.welcome.show()
        self._assistant_body = None
        self._streaming_text = ""

    def send_message(self) -> None:
        prompt = self.composer.toPlainText().strip()
        model = self.model_combo.currentText().strip()
        if not prompt or not model or (self.worker and self.worker.isRunning()):
            return
        self.history.append({"role": "user", "content": prompt})
        self._add_message("user", prompt)
        self._assistant_body = self._add_message("assistant", "", streaming=True)
        self._streaming_text = ""
        self.composer.clear()
        self.composer.setEnabled(False)
        self.send_button.setEnabled(False)
        self.worker = ChatWorker(self.endpoint, model, list(self.history), self.temperature)
        self.worker.chunk.connect(self._on_chunk)
        self.worker.completed.connect(self._on_completed)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _on_chunk(self, chunk: str) -> None:
        self._streaming_text += chunk
        if self._assistant_body:
            self._assistant_body.setText(self._streaming_text)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_completed(self, _metadata: dict) -> None:
        if self._streaming_text:
            self.history.append({"role": "assistant", "content": self._streaming_text})
        elif self._assistant_body:
            self._assistant_body.setText("The model returned an empty response.")

    def _on_failed(self, message: str) -> None:
        if self._assistant_body:
            self._assistant_body.setText(f"Unable to generate a response: {message}")
        if self._streaming_text:
            self.history.append({"role": "assistant", "content": self._streaming_text})

    def _worker_finished(self) -> None:
        self.composer.setEnabled(True)
        self.send_button.setEnabled(self.model_combo.count() > 0)
        self.composer.setFocus()
        self.worker = None
