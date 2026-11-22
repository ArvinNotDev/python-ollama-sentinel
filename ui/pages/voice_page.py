from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QProgressBar, QVBoxLayout, QWidget,
)

from core.settings import SettingsStore
from core.speech.whisper_manager import WHISPER_MODELS, WhisperModelManager
from ui.audio_recorder import AudioRecorder
from ui.mic_button import CircularMicButton
from ui.workers import WhisperDownloadWorker, WhisperTranscriptionWorker
from ui.theme import app_icon


class VoicePage(QWidget):
    insert_into_chat = Signal(str)
    status_message = Signal(str)
    speech_preferences_changed = Signal(str, str)

    def __init__(self, settings: SettingsStore, whisper_manager: WhisperModelManager, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.whisper_manager = whisper_manager
        self.download_worker: WhisperDownloadWorker | None = None
        self.transcription_worker: WhisperTranscriptionWorker | None = None
        self.recorder = AudioRecorder(self)
        self.audio_path: str | None = None
        self.recorder.recording_changed.connect(self._on_recording_changed)
        self.recorder.recording_finished.connect(self._on_recording_finished)
        self.recorder.failed.connect(self._on_error)

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 22)
        root.setSpacing(16)
        title = QLabel("Voice Studio")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Record speech and turn it into editable text with a local Whisper model.")
        subtitle.setObjectName("PageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        model_card = QFrame()
        model_card.setObjectName("SettingCard")
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(20, 18, 20, 18)
        model_layout.setSpacing(10)
        section = QLabel("Local speech model")
        section.setObjectName("SectionTitle")
        description = QLabel("Whisper models are free to download and run locally. Select a size, download it once, then use voice input without sending audio to a cloud provider.")
        description.setObjectName("Muted")
        description.setWordWrap(True)
        model_row = QHBoxLayout()
        self.model_combo = QComboBox()
        for model_name, details in WHISPER_MODELS.items():
            self.model_combo.addItem(f"{model_name}  ·  {details['description']}", model_name)
        current_index = self.model_combo.findData(self.settings.speech_default_model)
        self.model_combo.setCurrentIndex(max(0, current_index))
        self.model_combo.currentIndexChanged.connect(self._model_changed)
        self.download_button = QPushButton("Download model")
        self.download_button.setIcon(app_icon("mdi6.download", "#FFFFFF"))
        self.download_button.setObjectName("PrimaryButton")
        self.download_button.clicked.connect(self._download_selected)
        model_row.addWidget(self.model_combo, 1)
        model_row.addWidget(self.download_button)
        self.model_status = QLabel("")
        self.model_status.setObjectName("Muted")
        model_layout.addWidget(section)
        model_layout.addWidget(description)
        model_layout.addLayout(model_row)
        model_layout.addWidget(self.model_status)
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.hide()
        model_layout.addWidget(self.download_progress)
        root.addWidget(model_card)

        recording_card = QFrame()
        recording_card.setObjectName("SettingCard")
        recording_layout = QVBoxLayout(recording_card)
        recording_layout.setContentsMargins(20, 18, 20, 18)
        recording_layout.setSpacing(12)
        recording_title = QLabel("Record and transcribe")
        recording_title.setObjectName("SectionTitle")
        record_row = QHBoxLayout()
        self.mic_button = CircularMicButton()
        self.mic_button.clicked.connect(self._toggle_recording)
        self.recording_status = QLabel("Ready when you are. Your recording stays on this device.")
        self.recording_status.setObjectName("Muted")
        self.language_combo = QComboBox()
        self.language_combo.addItem("Auto detect", "auto")
        self.language_combo.addItem("Persian", "fa")
        self.language_combo.addItem("English", "en")
        language_index = self.language_combo.findData(self.settings.speech_language)
        self.language_combo.setCurrentIndex(max(0, language_index))
        self.language_combo.currentIndexChanged.connect(self._save_language)
        record_row.addWidget(self.mic_button)
        record_row.addWidget(self.recording_status, 1)
        record_row.addWidget(QLabel("Language"))
        record_row.addWidget(self.language_combo)
        recording_layout.addWidget(recording_title)
        recording_layout.addLayout(record_row)
        root.addWidget(recording_card)

        transcript_card = QFrame()
        transcript_card.setObjectName("SettingCard")
        transcript_layout = QVBoxLayout(transcript_card)
        transcript_layout.setContentsMargins(20, 18, 20, 18)
        transcript_layout.setSpacing(10)
        transcript_header = QHBoxLayout()
        transcript_title = QLabel("Transcript")
        transcript_title.setObjectName("SectionTitle")
        transcript_header.addWidget(transcript_title)
        transcript_header.addStretch()
        self.copy_button = QPushButton("Copy")
        self.copy_button.setIcon(app_icon("mdi6.content-copy", "#B7BEC9"))
        self.copy_button.clicked.connect(self._copy_transcript)
        self.insert_button = QPushButton("Insert into Chat")
        self.insert_button.setIcon(app_icon("mdi6.chat-plus-outline", "#FFFFFF"))
        self.insert_button.setObjectName("PrimaryButton")
        self.insert_button.clicked.connect(self._insert_transcript)
        transcript_header.addWidget(self.copy_button)
        transcript_header.addWidget(self.insert_button)
        self.transcript = QPlainTextEdit()
        self.transcript.setPlaceholderText("Your recognized speech will appear here. You can edit it before copying or inserting it into Chat.")
        self.transcript.setMinimumHeight(190)
        transcript_layout.addLayout(transcript_header)
        transcript_layout.addWidget(self.transcript)
        root.addWidget(transcript_card, 1)
        self._refresh_model_state()

    def _selected_model(self) -> str:
        return str(self.model_combo.currentData() or "base")

    def _model_changed(self, _index: int = -1) -> None:
        model_name = self._selected_model()
        language = str(self.language_combo.currentData() or "auto")
        self.settings.set("speech_default_model", model_name)
        self.speech_preferences_changed.emit(model_name, language)
        self._refresh_model_state()

    def _save_language(self, _index: int = -1) -> None:
        language = str(self.language_combo.currentData() or "auto")
        self.settings.set("speech_language", language)
        self.speech_preferences_changed.emit(self._selected_model(), language)

    def apply_settings(self, models_directory: str, model_name: str, language: str) -> None:
        self.whisper_manager.set_models_directory(models_directory)
        self.model_combo.blockSignals(True)
        model_index = self.model_combo.findData(model_name)
        self.model_combo.setCurrentIndex(max(0, model_index))
        self.model_combo.blockSignals(False)
        self.language_combo.blockSignals(True)
        language_index = self.language_combo.findData(language)
        self.language_combo.setCurrentIndex(max(0, language_index))
        self.language_combo.blockSignals(False)
        self._refresh_model_state()

    def _refresh_model_state(self) -> None:
        name = self._selected_model()
        installed = self.whisper_manager.is_installed(name)
        self.model_status.setText(
            f"✓ {name} is installed and ready for offline transcription."
            if installed else f"{name} is not installed yet. Download it to enable local speech recognition."
        )
        self.download_button.setText("Download model again" if installed else "Download model")

    def _download_selected(self) -> None:
        if self.download_worker and self.download_worker.isRunning():
            return
        name = self._selected_model()
        if self.whisper_manager.is_installed(name):
            self._refresh_model_state()
            return
        self.download_button.setEnabled(False)
        self.download_progress.setValue(0)
        self.download_progress.show()
        self.mic_button.set_download_progress(0)
        self.model_status.setText(f"Downloading Whisper {name}…")
        worker = WhisperDownloadWorker(self.whisper_manager, name, self)
        self.download_worker = worker
        worker.progress.connect(self._on_download_progress)
        worker.completed.connect(lambda _path: self._on_download_completed(name))
        worker.failed.connect(self._on_download_failed)
        worker.finished.connect(lambda current=worker: self._download_finished(current))
        worker.start()

    def _on_download_progress(self, current: int, total: int) -> None:
        percent = int(current * 100 / total) if total > 0 else 0
        self.download_progress.setValue(percent)
        self.mic_button.set_download_progress(percent)
        self.model_status.setText(f"Downloading model files… {percent}%")

    def _on_download_completed(self, model_name: str) -> None:
        self.mic_button.set_download_progress(None)
        self.download_progress.setValue(100)
        self.model_status.setText(f"✓ Whisper {model_name} downloaded and ready.")
        self._refresh_model_state()

    def _on_download_failed(self, message: str) -> None:
        self.mic_button.set_download_progress(None)
        self.model_status.setText(f"Download failed: {message}")
        self.status_message.emit(message)

    def _download_finished(self, worker: WhisperDownloadWorker) -> None:
        if self.download_worker is worker:
            self.download_worker = None
        self.download_button.setEnabled(True)
        worker.deleteLater()

    def _toggle_recording(self) -> None:
        if self.transcription_worker and self.transcription_worker.isRunning():
            return
        if self.download_worker and self.download_worker.isRunning():
            return
        if self.recorder.is_recording:
            self.recorder.stop_recording()
            return
        name = self._selected_model()
        if self.whisper_manager.is_installed(name):
            self.recorder.start_recording()
            return
        answer = QMessageBox.question(
            self, "Download Whisper model",
            f"Whisper {name} is not installed.\n\nDownload this free local model now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._download_selected()

    def _on_recording_changed(self, recording: bool) -> None:
        self.mic_button.set_recording(recording)
        self.mic_button.setEnabled(True)
        self.recording_status.setText(
            "Listening… select the microphone again to finish recording."
            if recording else "Recording stopped. Preparing local transcription…"
        )

    def _on_recording_finished(self, audio_path: str) -> None:
        self.audio_path = audio_path
        self.recording_status.setText(f"Transcribing with local Whisper {self._selected_model()}…")
        self.mic_button.setEnabled(False)
        language = str(self.language_combo.currentData() or "auto")
        worker = WhisperTranscriptionWorker(
            self.whisper_manager, audio_path, self._selected_model(),
            language=None if language == "auto" else language, parent=self,
        )
        self.transcription_worker = worker
        worker.completed.connect(self._on_transcribed)
        worker.failed.connect(self._on_error)
        worker.finished.connect(lambda current=worker: self._transcription_finished(current))
        worker.start()

    def _on_transcribed(self, text: str, language: str) -> None:
        existing = self.transcript.toPlainText().strip()
        self.transcript.setPlainText(f"{existing}\n{text}" if existing else text)
        self.recording_status.setText(f"Transcribed locally · detected language: {language}")
        self.mic_button.setEnabled(True)

    def _on_error(self, message: str) -> None:
        self.recording_status.setText(message)
        self.mic_button.setEnabled(True)
        self.mic_button.set_recording(False)
        self.mic_button.set_download_progress(None)
        if self.audio_path:
            Path(self.audio_path).unlink(missing_ok=True)
            self.audio_path = None

    def _transcription_finished(self, worker: WhisperTranscriptionWorker) -> None:
        if self.transcription_worker is worker:
            self.transcription_worker = None
        self.audio_path = None
        worker.deleteLater()

    def _copy_transcript(self) -> None:
        text = self.transcript.toPlainText().strip()
        if text:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            self.status_message.emit("Transcript copied.")

    def _insert_transcript(self) -> None:
        text = self.transcript.toPlainText().strip()
        if text:
            self.insert_into_chat.emit(text)

    def set_models_directory(self, path: str) -> None:
        self.whisper_manager.set_models_directory(path)
        self._refresh_model_state()
