from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation, Qt, QTimer, QSize
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QAbstractItemView, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from core.ollama.process_manager import OllamaProcessManager
from core.settings import SettingsStore
from core.speech.whisper_manager import WhisperModelManager
from ui.pages.chat_page import ChatPage
from ui.pages.models_page import ModelsPage
from ui.pages.settings_page import SettingsPage
from ui.pages.voice_page import VoicePage
from ui.theme import app_icon


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsStore | None = None) -> None:
        super().__init__()
        self.settings = settings or SettingsStore()
        self.process_manager = OllamaProcessManager()
        self.whisper_manager = WhisperModelManager(self.settings.speech_models_directory)
        self._navigation_animation: QPropertyAnimation | None = None
        self.setWindowTitle("Ollama Sentinel")
        self.setObjectName("MainWindow")
        self.resize(1360, 860)
        self.setMinimumSize(1080, 700)

        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(258)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(17, 20, 17, 18)
        sidebar_layout.setSpacing(7)

        brand_row = QHBoxLayout()
        brand_mark = QLabel()
        brand_mark.setObjectName("BrandMark")
        brand_mark.setFixedSize(36, 36)
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setPixmap(app_icon("mdi6.robot-outline", "#FFFFFF").pixmap(QSize(21, 21)))
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_name = QLabel("Ollama Sentinel")
        brand_name.setObjectName("Brand")
        brand_row.addWidget(brand_mark)
        brand_row.addWidget(brand_name)
        brand_row.addStretch()
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addSpacing(20)
        self._nav_items = (
            ("Chat", "mdi6.chat-outline", 0),
            ("Models", "mdi6.cube-outline", 1),
            ("Voice", "mdi6.waveform", 2),
            ("Settings", "mdi6.tune-variant", 3),
        )

        self.new_chat_button = QPushButton("New chat")
        self.new_chat_button.setIcon(app_icon("mdi6.plus", "#FFFFFF"))
        self.new_chat_button.setIconSize(QSize(17, 17))
        self.new_chat_button.setObjectName("NewChatButton")
        self.new_chat_button.setFixedHeight(39)
        sidebar_layout.addWidget(self.new_chat_button)

        history_label = QLabel("YOUR CHATS")
        history_label.setObjectName("Muted")
        history_label.setStyleSheet(
            "font-size: 10px; font-weight: 700; letter-spacing: 1px; padding: 7px 5px 2px;"
        )
        sidebar_layout.addWidget(history_label)
        self.chat_history_list = QListWidget()
        self.chat_history_list.setObjectName("ChatHistoryList")
        self.chat_history_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.chat_history_list.setSpacing(3)
        self.chat_history_list.itemClicked.connect(self._open_chat_from_sidebar)
        sidebar_layout.addWidget(self.chat_history_list, 1)

        server_card = QFrame()
        server_card.setObjectName("ServerCard")
        server_layout = QVBoxLayout(server_card)
        server_layout.setContentsMargins(12, 12, 12, 12)
        status_heading = QLabel("OLLAMA SERVER")
        status_heading.setObjectName("Muted")
        status_heading.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        self.server_status = QLabel("●  Checking connection")
        self.server_status.setObjectName("StatusDot")
        self.server_status.setStyleSheet("color: #d2b46d;")
        self.model_count = QLabel("Model library · —")
        self.model_count.setObjectName("Muted")
        self.model_count.setWordWrap(True)
        server_layout.addWidget(status_heading)
        server_layout.addWidget(self.server_status)
        server_layout.addWidget(self.model_count)
        sidebar_layout.addWidget(server_card)
        root_layout.addWidget(sidebar)

        content = QWidget()
        content.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(64)
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(24, 0, 24, 0)
        top_layout.setSpacing(8)
        self.breadcrumb = QLabel("Workspace  /  Chat")
        self.breadcrumb.setObjectName("Muted")
        self.endpoint_hint = QLabel(self.settings.endpoint)
        self.endpoint_hint.setObjectName("Muted")
        top_layout.addWidget(self.breadcrumb)
        top_layout.addStretch(1)
        self.nav_buttons: list[QPushButton] = []
        for label, icon_name, index in self._nav_items:
            button = QPushButton(label)
            button.setIcon(app_icon(icon_name))
            button.setIconSize(QSize(16, 16))
            button.setObjectName("NavTab")
            button.setCheckable(True)
            button.setFixedHeight(35)
            button.clicked.connect(lambda _checked=False, page=index: self.navigate(page))
            self.nav_buttons.append(button)
            top_layout.addWidget(button)
        top_layout.addSpacing(12)
        top_layout.addWidget(self.endpoint_hint)
        content_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        self.chat_page = ChatPage(
            self.settings.endpoint,
            float(self.settings.get("temperature", 0.7)),
            settings=self.settings,
            whisper_manager=self.whisper_manager,
        )
        self.new_chat_button.clicked.connect(self._start_new_chat)
        self.chat_page.conversations_changed.connect(self._refresh_chat_history)
        self.models_page = ModelsPage(self.settings.endpoint)
        self.voice_page = VoicePage(self.settings, self.whisper_manager)
        self.settings_page = SettingsPage(self.settings)
        self.stack.addWidget(self.chat_page)
        self.stack.addWidget(self.models_page)
        self.stack.addWidget(self.voice_page)
        self.stack.addWidget(self.settings_page)
        content_layout.addWidget(self.stack, 1)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        self.models_page.models_changed.connect(self._models_updated)
        self.models_page.connection_changed.connect(self._connection_updated)
        self.models_page.status_message.connect(self._show_status)
        self.settings_page.status_message.connect(self._show_status)
        self.settings_page.settings_changed.connect(self._settings_updated)
        self.settings_page.speech_settings_changed.connect(self._speech_settings_updated)
        self.settings_page.api_profiles_changed.connect(self._api_profiles_updated)
        self.voice_page.insert_into_chat.connect(self._insert_voice_text)
        self.voice_page.speech_preferences_changed.connect(self._voice_preferences_updated)
        self.voice_page.status_message.connect(self._show_status)
        self.settings_page.launch_server_requested.connect(self._launch_managed_server)
        self.chat_page.set_remote_profiles(self.settings.list_api_profiles())
        self.chat_page.notify_conversations_changed()
        self.navigate(0)
        QTimer.singleShot(250, self.models_page.refresh_models)

    def _start_new_chat(self) -> None:
        self.chat_page.new_chat()
        self.navigate(0)

    def _open_chat_from_sidebar(self, item: QListWidgetItem) -> None:
        conversation_id = item.data(Qt.ItemDataRole.UserRole)
        if conversation_id and self.chat_page.open_conversation(str(conversation_id)):
            self.navigate(0)

    def _refresh_chat_history(self, conversations: list) -> None:
        self.chat_history_list.blockSignals(True)
        self.chat_history_list.clear()
        active_item = None
        for conversation in conversations:
            item = QListWidgetItem(str(conversation.get("title") or "New chat"))
            item.setData(Qt.ItemDataRole.UserRole, str(conversation.get("id", "")))
            updated_at = str(conversation.get("updated_at", ""))
            if updated_at:
                item.setToolTip(updated_at)
            self.chat_history_list.addItem(item)
            if conversation.get("active"):
                active_item = item
        if not conversations:
            empty_item = QListWidgetItem("No saved chats yet")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.chat_history_list.addItem(empty_item)
        elif active_item is not None:
            self.chat_history_list.setCurrentItem(active_item)
        self.chat_history_list.blockSignals(False)

    def navigate(self, index: int) -> None:
        if index != self.stack.currentIndex():
            if self._navigation_animation and self._navigation_animation.state() == QAbstractAnimation.State.Running:
                self._navigation_animation.stop()
            self.stack.setCurrentIndex(index)
            page = self.stack.currentWidget()
            effect = QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(effect)
            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.setDuration(150)
            animation.setStartValue(0.82)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.finished.connect(lambda current=page: current.setGraphicsEffect(None))
            self._navigation_animation = animation
            animation.start()
        for position, button in enumerate(self.nav_buttons):
            button.setChecked(position == index)
            button.setIcon(app_icon(self._nav_items[position][1], "#C7BDF5" if position == index else "#9299A6"))
        labels = ("Workspace  /  Chat", "Workspace  /  Models", "Workspace  /  Voice", "Workspace  /  Settings")
        self.breadcrumb.setText(labels[index])
        if index == 1:
            self.models_page.refresh_models()

    def _models_updated(self, models: list[dict]) -> None:
        self.chat_page.set_models(models)
        count = len(models)
        self.model_count.setText(f"Model library · {count} model{'s' if count != 1 else ''}")

    def _speech_settings_updated(self, models_directory: str, model_name: str, language: str) -> None:
        self.whisper_manager.set_models_directory(models_directory)
        self.settings.set("speech_default_model", model_name)
        self.settings.set("speech_language", language)
        self.chat_page.set_speech_settings(model_name, language, models_directory)
        self.voice_page.apply_settings(models_directory, model_name, language)
        self._show_status("Voice settings saved.")

    def _voice_preferences_updated(self, model_name: str, language: str) -> None:
        self.settings.set("speech_default_model", model_name)
        self.settings.set("speech_language", language)
        model_index = self.settings_page.speech_model_combo.findData(model_name)
        self.settings_page.speech_model_combo.setCurrentIndex(max(0, model_index))
        language_index = self.settings_page.speech_language_combo.findData(language)
        self.settings_page.speech_language_combo.setCurrentIndex(max(0, language_index))

    def _insert_voice_text(self, text: str) -> None:
        self.chat_page.insert_voice_text(text)
        self.navigate(0)

    def _api_profiles_updated(self, profiles: list[dict]) -> None:
        self.chat_page.set_remote_profiles(profiles)

    def _connection_updated(self, connected: bool) -> None:
        self.server_status.setText("●  Connected" if connected else "●  Not connected")
        self.server_status.setStyleSheet("color: #45d69a;" if connected else "color: #ef7884;")

    def _show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 7000)

    def _settings_updated(self, endpoint: str, temperature: float) -> None:
        self.chat_page.set_endpoint(endpoint)
        self.chat_page.set_temperature(temperature)
        self.models_page.set_endpoint(endpoint)
        self.endpoint_hint.setText(endpoint)
        self.server_status.setText("●  Checking connection")
        self.server_status.setStyleSheet("color: #d2b46d;")
        self.models_page.refresh_models()

    def _launch_managed_server(self) -> None:
        started, message = self.process_manager.start(
            self.settings.models_directory,
            self.settings.endpoint,
            self.settings.ollama_executable,
        )
        self._show_status(message)
        if not started:
            QMessageBox.information(self, "Ollama server", message)
            return
        self.server_status.setText("●  Starting Ollama")
        self.server_status.setStyleSheet("color: #d2b46d;")
        self._poll_server_start(0)

    def _poll_server_start(self, attempt: int) -> None:
        if attempt >= 20:
            self._show_status("Ollama did not become available. Check the installation and server logs.")
            self.server_status.setText("●  Not connected")
            self.server_status.setStyleSheet("color: #ef7884;")
            return
        from core.ollama.ollama_commands import OllamaClient
        client = OllamaClient(self.settings.endpoint, timeout=1.0)
        available = client.is_available(timeout=0.8)
        client.close()
        if available:
            self.server_status.setText("●  Connected · app managed")
            self.server_status.setStyleSheet("color: #45d69a;")
            self.models_page.refresh_models()
            return
        QTimer.singleShot(750, lambda: self._poll_server_start(attempt + 1))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.chat_page.save_current_conversation()
        self.process_manager.stop()
        super().closeEvent(event)
