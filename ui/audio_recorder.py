"""Microphone capture using Qt Multimedia, without an external audio backend."""

from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices


class AudioRecorder(QObject):
    recording_changed = Signal(bool)
    recording_finished = Signal(str)
    failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source: QAudioSource | None = None
        self._device = None
        self._chunks = bytearray()
        self._sample_rate = 16000
        self._channels = 1
        self._is_recording = False

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start_recording(self) -> None:
        if self._is_recording:
            return
        input_device = QMediaDevices.defaultAudioInput()
        if input_device.isNull():
            self.failed.emit("No microphone was found. Connect or enable a microphone and try again.")
            return

        audio_format = None
        for sample_rate in (16000, 48000, 44100):
            candidate = QAudioFormat()
            candidate.setSampleRate(sample_rate)
            candidate.setChannelCount(1)
            candidate.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            if input_device.isFormatSupported(candidate):
                audio_format = candidate
                break

        if audio_format is None:
            preferred = input_device.preferredFormat()
            if preferred.sampleFormat() == QAudioFormat.SampleFormat.Int16:
                audio_format = preferred
        if audio_format is None:
            self.failed.emit("The selected microphone does not support a compatible 16-bit PCM recording format.")
            return

        self._sample_rate = audio_format.sampleRate()
        self._channels = audio_format.channelCount()
        self._chunks.clear()
        self._source = QAudioSource(input_device, audio_format, self)
        self._device = self._source.start()
        if self._device is None or self._source.error().value != 0:
            self._source.stop()
            self._source = None
            self._device = None
            self.failed.emit("Could not start microphone capture. Check microphone permissions and audio device settings.")
            return

        self._device.readyRead.connect(self._read_available)
        self._is_recording = True
        self.recording_changed.emit(True)

    def _read_available(self) -> None:
        if self._device is not None:
            data = self._device.readAll()
            if data:
                self._chunks.extend(bytes(data))

    def stop_recording(self) -> None:
        if not self._is_recording:
            return
        self._read_available()
        if self._source is not None:
            self._source.stop()
        self._source = None
        self._device = None
        self._is_recording = False
        self.recording_changed.emit(False)

        minimum_bytes = int(self._sample_rate * self._channels * 2 * 0.15)
        if len(self._chunks) < minimum_bytes:
            self._chunks.clear()
            self.failed.emit("The recording is too short. Hold the microphone for a little longer.")
            return

        descriptor, file_path = tempfile.mkstemp(prefix="ollama-sentinel-voice-", suffix=".wav")
        os.close(descriptor)
        try:
            with wave.open(file_path, "wb") as audio_file:
                audio_file.setnchannels(self._channels)
                audio_file.setsampwidth(2)
                audio_file.setframerate(self._sample_rate)
                audio_file.writeframes(bytes(self._chunks))
        except OSError as exc:
            Path(file_path).unlink(missing_ok=True)
            self.failed.emit(f"Could not save the voice recording: {exc}")
            return
        finally:
            self._chunks.clear()
        self.recording_finished.emit(file_path)

    def discard_recording(self) -> None:
        if self._source is not None:
            self._source.stop()
        self._source = None
        self._device = None
        self._chunks.clear()
        was_recording = self._is_recording
        self._is_recording = False
        if was_recording:
            self.recording_changed.emit(False)
