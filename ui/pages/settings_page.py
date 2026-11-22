from __future__ import annotations

import uuid
from urllib.parse import urlparse

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from core.providers import PROVIDER_DEFAULTS
from core.secrets import SecretStoreError
from core.settings import SettingsStore
from core.speech.whisper_manager import WHISPER_MODELS
from ui.workers import ProviderModelsWorker


class SettingsPage(QWidget):
    settings_changed = Signal(str, float)
    speech_settings_changed = Signal(str, str, str)
    api_profiles_changed = Signal(list)
    launch_server_requested = Signal()
    status_message = Signal(str)

    def __init__(self, settings: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.current_profile_id: str | None = None
        self.provider_worker: ProviderModelsWorker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(34, 27, 34, 24)
        root.setSpacing(17)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Manage your local runtime, cloud providers and model behavior.")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        self._build_api_connections(root)
        self._build_ollama_connection(root)
        self._build_storage(root)
        self._build_speech_settings(root)
        self._build_generation(root)

        actions = QHBoxLayout()
        actions.addStretch()
        self.save_button = QPushButton("Save settings")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.save_settings)
        actions.addWidget(self.save_button)
        root.addLayout(actions)
        root.addStretch(1)
        self._refresh_profiles()
        self._on_provider_changed()

    def _card(self, title: str, description: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("SettingCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        copy = QLabel(description)
        copy.setObjectName("Muted")
        copy.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(copy)
        return card, layout

    def _build_api_connections(self, root: QVBoxLayout) -> None:
        card, layout = self._card(
            "AI API providers",
            "Connect cloud models with your own API credentials. Add multiple providers and switch between their models directly from Chat.",
        )
        saved_row = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(220)
        self.profile_combo.currentIndexChanged.connect(self._load_selected_profile)
        self.new_profile_button = QPushButton("＋  New connection")
        self.new_profile_button.clicked.connect(self._new_profile)
        saved_row.addWidget(QLabel("Saved connections"))
        saved_row.addWidget(self.profile_combo, 1)
        saved_row.addWidget(self.new_profile_button)
        layout.addLayout(saved_row)

        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText("Connection name, e.g. Personal OpenAI")
        self.provider_combo = QComboBox()
        for provider_id, config in PROVIDER_DEFAULTS.items():
            self.provider_combo.addItem(config["label"], provider_id)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://api.example.com/v1")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Paste API key (leave blank to keep the saved key)")
        self.api_key_status = QLabel("API keys are stored in your operating system credential manager.")
        self.api_key_status.setObjectName("Muted")

        self.show_key_button = QPushButton("Show")
        self.show_key_button.setObjectName("GhostButton")
        self.show_key_button.setCheckable(True)
        self.show_key_button.toggled.connect(
            lambda shown: (
                self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password),
                self.show_key_button.setText("Hide" if shown else "Show"),
            )
        )
        key_row = QHBoxLayout()
        key_row.addWidget(self.api_key_input, 1)
        key_row.addWidget(self.show_key_button)

        models_label = QLabel("Model IDs")
        models_label.setObjectName("SectionTitle")
        models_copy = QLabel(
            "Fetch models from the provider, or add model IDs manually (one per line). These entries appear in the Chat model selector."
        )
        models_copy.setObjectName("Muted")
        models_copy.setWordWrap(True)
        self.models_input = QPlainTextEdit()
        self.models_input.setPlaceholderText("gpt-model-name\nanother-model-id")
        self.models_input.setMinimumHeight(76)
        self.models_input.setMaximumHeight(125)

        self.provider_status = QLabel("Not tested")
        self.provider_status.setObjectName("Muted")
        action_row = QHBoxLayout()
        self.fetch_models_button = QPushButton("Fetch models")
        self.fetch_models_button.clicked.connect(self._fetch_provider_models)
        self.test_provider_button = QPushButton("Test connection")
        self.test_provider_button.clicked.connect(self._fetch_provider_models)
        self.save_provider_button = QPushButton("Save connection")
        self.save_provider_button.setObjectName("PrimaryButton")
        self.save_provider_button.clicked.connect(self._save_provider)
        self.remove_provider_button = QPushButton("Remove")
        self.remove_provider_button.setObjectName("DangerButton")
        self.remove_provider_button.clicked.connect(self._remove_provider)
        action_row.addWidget(self.fetch_models_button)
        action_row.addWidget(self.test_provider_button)
        action_row.addStretch()
        action_row.addWidget(self.remove_provider_button)
        action_row.addWidget(self.save_provider_button)

        layout.addWidget(QLabel("Connection name"))
        layout.addWidget(self.profile_name_input)
        layout.addWidget(QLabel("Provider"))
        layout.addWidget(self.provider_combo)
        layout.addWidget(QLabel("API base URL"))
        layout.addWidget(self.base_url_input)
        layout.addWidget(QLabel("API key"))
        layout.addLayout(key_row)
        layout.addWidget(self.api_key_status)
        layout.addWidget(models_label)
        layout.addWidget(models_copy)
        layout.addWidget(self.models_input)
        layout.addWidget(self.provider_status)
        layout.addLayout(action_row)
        root.addWidget(card)

    def _build_ollama_connection(self, root: QVBoxLayout) -> None:
        card, layout = self._card(
            "Local Ollama connection",
            "Connect to a local or self-hosted Ollama server. The default address is usually correct for a local installation.",
        )
        self.endpoint_input = QLineEdit(self.settings.endpoint)
        self.endpoint_input.setPlaceholderText("http://127.0.0.1:11434")
        layout.addWidget(self.endpoint_input)
        root.addWidget(card)

    def _build_storage(self, root: QVBoxLayout) -> None:
        card, layout = self._card(
            "Model storage",
            "Choose where Ollama should keep downloaded model files. This path is applied when Ollama is launched by this app; an already-running Ollama service keeps its existing environment.",
        )
        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit(self.settings.models_directory)
        self.folder_input.setPlaceholderText("Choose a folder for model files")
        self.browse_folder_button = QPushButton("Browse…")
        self.browse_folder_button.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.browse_folder_button)
        exe_row = QHBoxLayout()
        self.executable_input = QLineEdit(self.settings.ollama_executable)
        self.executable_input.setPlaceholderText("Optional: path to ollama.exe (auto-detected when empty)")
        self.browse_executable_button = QPushButton("Find Ollama…")
        self.browse_executable_button.clicked.connect(self._browse_executable)
        exe_row.addWidget(self.executable_input, 1)
        exe_row.addWidget(self.browse_executable_button)
        self.launch_button = QPushButton("Launch Ollama with this folder")
        self.launch_button.setObjectName("PrimaryButton")
        self.launch_button.clicked.connect(self._launch_server)
        layout.addLayout(folder_row)
        layout.addLayout(exe_row)
        layout.addWidget(self.launch_button, 0, Qt.AlignmentFlag.AlignLeft)
        root.addWidget(card)

    def _build_speech_settings(self, root: QVBoxLayout) -> None:
        card, layout = self._card(
            "Voice input · Whisper",
            "Manage free multilingual speech-to-text models used by Voice Studio and the microphone button in Chat. Models are downloaded once and run locally.",
        )
        folder_row = QHBoxLayout()
        self.speech_folder_input = QLineEdit(self.settings.speech_models_directory)
        self.speech_folder_input.setPlaceholderText("Choose a folder for Whisper model files")
        self.browse_speech_folder_button = QPushButton("Browse…")
        self.browse_speech_folder_button.clicked.connect(self._browse_speech_folder)
        folder_row.addWidget(self.speech_folder_input, 1)
        folder_row.addWidget(self.browse_speech_folder_button)

        preferences_row = QHBoxLayout()
        self.speech_model_combo = QComboBox()
        for name, details in WHISPER_MODELS.items():
            self.speech_model_combo.addItem(
                f"{name} · {details['description']}", name
            )
        model_index = self.speech_model_combo.findData(self.settings.speech_default_model)
        self.speech_model_combo.setCurrentIndex(max(0, model_index))
        self.speech_language_combo = QComboBox()
        self.speech_language_combo.addItem("Auto detect", "auto")
        self.speech_language_combo.addItem("Persian", "fa")
        self.speech_language_combo.addItem("English", "en")
        language_index = self.speech_language_combo.findData(self.settings.speech_language)
        self.speech_language_combo.setCurrentIndex(max(0, language_index))
        preferences_row.addWidget(QLabel("Default model"))
        preferences_row.addWidget(self.speech_model_combo, 1)
        preferences_row.addWidget(QLabel("Language"))
        preferences_row.addWidget(self.speech_language_combo)

        layout.addLayout(folder_row)
        layout.addLayout(preferences_row)
        root.addWidget(card)

    def _browse_speech_folder(self) -> None:
        start = self.speech_folder_input.text().strip()
        directory = QFileDialog.getExistingDirectory(self, "Choose Whisper model folder", start)
        if directory:
            self.speech_folder_input.setText(directory)

    def _build_generation(self, root: QVBoxLayout) -> None:
        card, layout = self._card(
            "Response behavior", "Set a default sampling temperature for local and remote chat models."
        )
        self.temperature_label = QLabel(f"Temperature  ·  {float(self.settings.get('temperature', 0.7)):.1f}")
        self.temperature_label.setObjectName("Muted")
        self.temperature = QSlider(Qt.Orientation.Horizontal)
        self.temperature.setRange(0, 20)
        self.temperature.setValue(round(float(self.settings.get("temperature", 0.7)) * 10))
        self.temperature.valueChanged.connect(
            lambda value: self.temperature_label.setText(f"Temperature  ·  {value / 10:.1f}")
        )
        layout.addWidget(self.temperature_label)
        layout.addWidget(self.temperature)
        root.addWidget(card)

    def _refresh_profiles(self, select_id: str | None = None) -> None:
        profiles = self.settings.list_api_profiles()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("＋  Add a connection", "")
        for profile in profiles:
            self.profile_combo.addItem(
                f"{profile.get('name', 'API connection')}  ·  {profile.get('provider', '')}",
                profile.get("id"),
            )
        target = select_id or self.current_profile_id
        index = self.profile_combo.findData(target) if target else 0
        self.profile_combo.setCurrentIndex(max(index, 0))
        self.profile_combo.blockSignals(False)
        if target and index > 0:
            self._load_profile_by_id(target)
        elif not target:
            self._clear_provider_form()

    def _clear_provider_form(self) -> None:
        self.current_profile_id = None
        self.profile_name_input.clear()
        self.provider_combo.setCurrentIndex(0)
        self.base_url_input.setText(PROVIDER_DEFAULTS["openai"]["base_url"])
        self.api_key_input.clear()
        self.api_key_status.setText("API keys are stored in your operating system credential manager.")
        self.models_input.clear()
        self.provider_status.setText("Not tested")
        self.remove_provider_button.setEnabled(False)
        self._on_provider_changed()

    def _new_profile(self) -> None:
        self._clear_provider_form()
        self.profile_combo.blockSignals(True)
        self.profile_combo.setCurrentIndex(0)
        self.profile_combo.blockSignals(False)
        self.profile_name_input.setFocus()

    def _load_selected_profile(self, index: int) -> None:
        profile_id = self.profile_combo.itemData(index)
        if profile_id:
            self._load_profile_by_id(profile_id)
        else:
            self._clear_provider_form()

    def _load_profile_by_id(self, profile_id: str) -> None:
        profile = self.settings.get_api_profile(profile_id)
        if not profile:
            self._clear_provider_form()
            return
        self.current_profile_id = profile_id
        self.profile_name_input.setText(profile.get("name", ""))
        provider_index = self.provider_combo.findData(profile.get("provider"))
        self.provider_combo.setCurrentIndex(max(provider_index, 0))
        self.base_url_input.setText(profile.get("base_url", ""))
        self.api_key_input.clear()
        try:
            has_key = bool(self.settings.get_api_key(profile_id))
            self.api_key_status.setText(
                "✓ API key saved securely. Leave the field empty to keep it."
                if has_key else "No API key saved for this connection."
            )
        except SecretStoreError as exc:
            self.api_key_status.setText(str(exc))
        self.models_input.setPlainText("\n".join(item.get("id", "") for item in profile.get("models", [])))
        self.provider_status.setText(f"{len(profile.get('models', []))} model(s) configured")
        self.remove_provider_button.setEnabled(True)
        self._on_provider_changed()

    def _on_provider_changed(self, _index: int = -1) -> None:
        provider_id = self.provider_combo.currentData()
        config = PROVIDER_DEFAULTS.get(provider_id, PROVIDER_DEFAULTS["openai_compatible"])
        current = self.base_url_input.text().strip()
        known_defaults = {item["base_url"] for item in PROVIDER_DEFAULTS.values() if item["base_url"]}
        if not current or current in known_defaults:
            self.base_url_input.setText(config["base_url"])
        self.base_url_input.setPlaceholderText(config["base_url"] or "https://your-provider.example/v1")
        self.api_key_input.setPlaceholderText(
            "Required API key" if config["requires_key"] else "Optional API key (leave blank for local endpoints)"
        )

    def _draft_profile(self) -> tuple[dict, dict, dict | None]:
        provider_id = self.provider_combo.currentData()
        config = PROVIDER_DEFAULTS.get(provider_id, PROVIDER_DEFAULTS["openai_compatible"])
        base_url = self.base_url_input.text().strip().rstrip("/") or config["base_url"]
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Enter a valid HTTP or HTTPS API base URL.")
        name = self.profile_name_input.text().strip()
        if not name:
            raise ValueError("Give this API connection a name.")
        model_ids = []
        for line in self.models_input.toPlainText().replace(",", "\n").splitlines():
            model_id = line.strip()
            if model_id and model_id not in model_ids:
                model_ids.append(model_id)
        existing = self.settings.get_api_profile(self.current_profile_id) if self.current_profile_id else None
        return {
            "id": self.current_profile_id or str(uuid.uuid4()),
            "name": name,
            "provider": provider_id,
            "base_url": base_url,
            "models": [{"id": item, "name": item} for item in model_ids],
        }, config, existing

    def _save_provider(self) -> dict | None:
        try:
            profile, config, existing = self._draft_profile()
            new_key = self.api_key_input.text().strip()
            existing_key = self.settings.get_api_key(profile["id"]) if existing else ""
            if config["requires_key"] and not (new_key or existing_key):
                self.status_message.emit("An API key is required for this provider.")
                return None
            if new_key:
                self.settings.set_api_key(profile["id"], new_key)
            saved = self.settings.save_api_profile(profile)
            self.current_profile_id = saved["id"]
            self.api_key_input.clear()
            self.api_key_status.setText(
                "✓ API key saved securely." if new_key or existing_key else "No API key is stored; this endpoint can be used without one."
            )
            self.remove_provider_button.setEnabled(True)
            self._refresh_profiles(saved["id"])
            self.api_profiles_changed.emit(self.settings.list_api_profiles())
            self.status_message.emit(f"Saved API connection: {saved['name']}.")
            return saved
        except (ValueError, SecretStoreError) as exc:
            self.status_message.emit(str(exc))
            return None

    def _fetch_provider_models(self) -> None:
        profile = self._save_provider()
        if not profile:
            return
        try:
            api_key = self.settings.get_api_key(profile["id"])
        except SecretStoreError as exc:
            self.status_message.emit(str(exc))
            return
        self.fetch_models_button.setEnabled(False)
        self.test_provider_button.setEnabled(False)
        self.provider_status.setText("Connecting and checking available models…")
        worker = ProviderModelsWorker(profile, api_key)
        self.provider_worker = worker
        worker.loaded.connect(self._provider_models_loaded)
        worker.failed.connect(self._provider_models_failed)
        worker.finished.connect(lambda current=worker: self._provider_worker_finished(current))
        worker.start()

    def _provider_models_loaded(self, models: list) -> None:
        self.models_input.setPlainText("\n".join(item["id"] for item in models))
        profile, _config, _existing = self._draft_profile()
        profile["models"] = models
        saved = self.settings.save_api_profile(profile)
        self.current_profile_id = saved["id"]
        self._refresh_profiles(saved["id"])
        self.api_profiles_changed.emit(self.settings.list_api_profiles())
        self.provider_status.setText(f"✓ Connected · {len(models)} model(s) found")
        self.status_message.emit(f"Provider connection successful. Found {len(models)} model(s).")

    def _provider_models_failed(self, message: str) -> None:
        self.provider_status.setText("Connection failed")
        self.status_message.emit(f"Provider connection failed: {message}")

    def _provider_worker_finished(self, worker: ProviderModelsWorker) -> None:
        if self.provider_worker is worker:
            self.provider_worker = None
        self.fetch_models_button.setEnabled(True)
        self.test_provider_button.setEnabled(True)
        worker.deleteLater()

    def _remove_provider(self) -> None:
        if not self.current_profile_id:
            return
        profile = self.settings.get_api_profile(self.current_profile_id) or {}
        answer = QMessageBox.question(
            self, "Remove API connection",
            f"Remove {profile.get('name', 'this connection')} and its saved API key?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.settings.delete_api_profile(self.current_profile_id)
        except SecretStoreError as exc:
            self.status_message.emit(str(exc))
            return
        self.current_profile_id = None
        self._refresh_profiles()
        self.api_profiles_changed.emit(self.settings.list_api_profiles())
        self.status_message.emit("API connection removed.")

    def _browse_folder(self) -> None:
        start = self.folder_input.text().strip()
        directory = QFileDialog.getExistingDirectory(self, "Choose model storage folder", start)
        if directory:
            self.folder_input.setText(directory)

    def _browse_executable(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Ollama executable", "", "Ollama executable (ollama.exe);;All files (*)"
        )
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
        speech_folder = self.speech_folder_input.text().strip()
        if not speech_folder:
            self.status_message.emit("Choose a folder for Whisper models first.")
            return False
        temperature = self.temperature.value() / 10
        speech_model = str(self.speech_model_combo.currentData() or "base")
        speech_language = str(self.speech_language_combo.currentData() or "auto")
        self.settings.set("temperature", temperature)
        self.settings.set("speech_models_directory", speech_folder)
        self.settings.set("speech_default_model", speech_model)
        self.settings.set("speech_language", speech_language)
        self.settings_changed.emit(endpoint, temperature)
        self.speech_settings_changed.emit(speech_folder, speech_model, speech_language)
        self.status_message.emit("Settings saved.")
        return True

    def _launch_server(self) -> None:
        if self.save_settings():
            self.launch_server_requested.emit()
