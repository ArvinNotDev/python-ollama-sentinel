from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from core.ollama.process_manager import OllamaProcessManager
from core.settings import SettingsStore
from ui.pages.chat_page import ChatPage
from ui.pages.models_page import ModelsPage
from ui.pages.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsStore | None = None) -> None:
        super().__init__()
        self.settings = settings or SettingsStore()
        self.process_manager = OllamaProcessManager()
        self._navigation_animation: QPropertyAnimation | None = None
        self.setWindowTitle("Ollama Sentinel")
        self.resize(1360, 860)
        self.setMinimumSize(1080, 700)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(228)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 21, 16, 18)
        sidebar_layout.setSpacing(9)

        brand_row = QHBoxLayout()
        brand_mark = QLabel("O")
        brand_mark.setObjectName("BrandMark")
        brand_mark.setFixedSize(34, 34)
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_name = QLabel("Ollama Sentinel")
        brand_name.setObjectName("Brand")
        brand_row.addWidget(brand_mark)
        brand_row.addWidget(brand_name)
        brand_row.addStretch()
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addSpacing(28)

        nav_label = QLabel("WORKSPACE")
        nav_label.setObjectName("Muted")
        nav_label.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 1px; padding-left: 7px;")
        sidebar_layout.addWidget(nav_label)
        self.nav_buttons: list[QPushButton] = []
        for label, icon, index in (("Chat", "◌", 0), ("Models", "▦", 1), ("Settings", "⚙", 2)):
            button = QPushButton(f"{icon}    {label}")
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, page=index: self.navigate(page))
            self.nav_buttons.append(button)
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch(1)
        server_card = QFrame()
        server_card.setObjectName("Surface")
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
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(58)
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(26, 0, 28, 0)
        self.breadcrumb = QLabel("Workspace  /  Chat")
        self.breadcrumb.setObjectName("Muted")
        self.endpoint_hint = QLabel(self.settings.endpoint)
        self.endpoint_hint.setObjectName("Muted")
        top_layout.addWidget(self.breadcrumb)
        top_layout.addStretch()
        top_layout.addWidget(self.endpoint_hint)
        content_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        self.chat_page = ChatPage(self.settings.endpoint, float(self.settings.get("temperature", 0.7)))
        self.models_page = ModelsPage(self.settings.endpoint)
        self.settings_page = SettingsPage(self.settings)
        self.stack.addWidget(self.chat_page)
        self.stack.addWidget(self.models_page)
        self.stack.addWidget(self.settings_page)
        content_layout.addWidget(self.stack, 1)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        self.models_page.models_changed.connect(self._models_updated)
        self.models_page.connection_changed.connect(self._connection_updated)
        self.models_page.status_message.connect(self._show_status)
        self.settings_page.status_message.connect(self._show_status)
        self.settings_page.settings_changed.connect(self._settings_updated)
        self.settings_page.launch_server_requested.connect(self._launch_managed_server)
        self.navigate(0)
        QTimer.singleShot(250, self.models_page.refresh_models)

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
        labels = ("Workspace  /  Chat", "Workspace  /  Models", "Workspace  /  Settings")
        self.breadcrumb.setText(labels[index])
        if index == 1:
            self.models_page.refresh_models()

    def _models_updated(self, models: list[dict]) -> None:
        self.chat_page.set_models(models)
        count = len(models)
        self.model_count.setText(f"Model library · {count} model{'s' if count != 1 else ''}")

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
        self.process_manager.stop()
        super().closeEvent(event)
