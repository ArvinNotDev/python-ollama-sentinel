from __future__ import annotations

from urllib.parse import urlparse

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)

from core.settings import SettingsStore


class SettingsPage(QWidget):
    settings_changed = Signal(str, float)
    launch_server_requested = Signal()
    status_message = Signal(str)

    def __init__(self, settings: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 27, 34, 24)
        root.setSpacing(17)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Configure your Ollama connection and local model storage.")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        connection = QFrame()
        connection.setObjectName("SettingCard")
        connection_layout = QVBoxLayout(connection)
        connection_layout.setContentsMargins(20, 18, 20, 18)
        connection_layout.setSpacing(10)
        connection_title = QLabel("Ollama connection")
        connection_title.setObjectName("SectionTitle")
        connection_copy = QLabel("Connect to a local or self-hosted Ollama server. The default address is usually correct for a local installation.")
        connection_copy.setObjectName("Muted")
        connection_copy.setWordWrap(True)
        self.endpoint_input = QLineEdit(settings.endpoint)
        self.endpoint_input.setPlaceholderText("http://127.0.0.1:11434")
        connection_layout.addWidget(connection_title)
        connection_layout.addWidget(connection_copy)
        connection_layout.addWidget(self.endpoint_input)
        root.addWidget(connection)

        storage = QFrame()
        storage.setObjectName("SettingCard")
        storage_layout = QVBoxLayout(storage)
        storage_layout.setContentsMargins(20, 18, 20, 18)
        storage_layout.setSpacing(10)
        storage_title = QLabel("Model storage")
        storage_title.setObjectName("SectionTitle")
        storage_copy = QLabel(
            "Choose where Ollama should keep downloaded model files. This path is applied when Ollama is launched by this app; an already-running Ollama service keeps its existing environment."
        )
        storage_copy.setObjectName("Muted")
        storage_copy.setWordWrap(True)
        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit(settings.models_directory)
        self.folder_input.setPlaceholderText("Choose a folder for model files")
        self.browse_folder_button = QPushButton("Browse…")
        self.browse_folder_button.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.browse_folder_button)
        exe_row = QHBoxLayout()
        self.executable_input = QLineEdit(settings.ollama_executable)
        self.executable_input.setPlaceholderText("Optional: path to ollama.exe (auto-detected when empty)")
        self.browse_executable_button = QPushButton("Find Ollama…")
        self.browse_executable_button.clicked.connect(self._browse_executable)
        exe_row.addWidget(self.executable_input, 1)
        exe_row.addWidget(self.browse_executable_button)
        self.launch_button = QPushButton("Launch Ollama with this folder")
        self.launch_button.setObjectName("PrimaryButton")
        self.launch_button.clicked.connect(self._launch_server)
        storage_layout.addWidget(storage_title)
        storage_layout.addWidget(storage_copy)
        storage_layout.addLayout(folder_row)
        storage_layout.addLayout(exe_row)
        storage_layout.addWidget(self.launch_button, 0, Qt.AlignmentFlag.AlignLeft)
        root.addWidget(storage)

        generation = QFrame()
        generation.setObjectName("SettingCard")
        generation_layout = QVBoxLayout(generation)
        generation_layout.setContentsMargins(20, 18, 20, 18)
        generation_layout.setSpacing(10)
        gen_title = QLabel("Response behavior")
        gen_title.setObjectName("SectionTitle")
        self.temperature_label = QLabel(f"Temperature  ·  {float(settings.get('temperature', 0.7)):.1f}")
        self.temperature_label.setObjectName("Muted")
        self.temperature = QSlider(Qt.Orientation.Horizontal)
        self.temperature.setRange(0, 20)
        self.temperature.setValue(round(float(settings.get("temperature", 0.7)) * 10))
        self.temperature.valueChanged.connect(lambda value: self.temperature_label.setText(f"Temperature  ·  {value / 10:.1f}"))
        generation_layout.addWidget(gen_title)
        generation_layout.addWidget(self.temperature_label)
        generation_layout.addWidget(self.temperature)
        root.addWidget(generation)

        actions = QHBoxLayout()
        actions.addStretch()
        self.save_button = QPushButton("Save settings")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.save_settings)
        actions.addWidget(self.save_button)
        root.addLayout(actions)
        root.addStretch(1)

    def _browse_folder(self) -> None:
        start = self.folder_input.text().strip()
        directory = QFileDialog.getExistingDirectory(self, "Choose model storage folder", start)
        if directory:
            self.folder_input.setText(directory)

    def _browse_executable(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Ollama executable", "", "Ollama executable (ollama.exe);;All files (*)")
        if path:
            self.executable_input.setText(path)

    def save_settings(self) -> bool:
        endpoint = self.endpoint_input.text().strip().rstrip("/")
        folder = self.folder_input.text().strip()
        executable = self.executable_input.text().strip()
        try:
            parsed_endpoint = urlparse(endpoint)
            valid_endpoint = parsed_endpoint.scheme in {"http", "https"} and bool(parsed_endpoint.hostname)
        except ValueError:
            valid_endpoint = False
        if not valid_endpoint:
            self.status_message.emit("Enter a valid Ollama HTTP or HTTPS address.")
            return False
        if not folder:
            self.status_message.emit("Choose a model storage folder first.")
            return False
        self.settings.set("endpoint", endpoint)
        self.settings.set("models_directory", folder)
        self.settings.set("ollama_executable", executable)
        temperature = self.temperature.value() / 10
        self.settings.set("temperature", temperature)
        self.settings_changed.emit(endpoint, temperature)
        self.status_message.emit("Settings saved.")
        return True

    def _launch_server(self) -> None:
        if self.save_settings():
            self.launch_server_requested.emit()
