from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton


class CircularMicButton(QPushButton):
    """Compact microphone control with an optional circular download indicator."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._progress: int | None = None
        self._recording = False
        self.setFixedSize(46, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Record voice")

    def set_download_progress(self, value: int | None) -> None:
        self._progress = None if value is None else max(0, min(100, int(value)))
        self.update()

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        self.setToolTip("Stop recording" if recording else "Record voice")
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._progress is not None or self._recording:
            painter.setBrush(QColor("#29233d" if self._recording else "#1b202b"))
            painter.drawEllipse(rect)

        ring_rect = self.rect().adjusted(1, 1, -1, -1)
        if self._progress is not None:
            painter.setPen(QPen(QColor("#363c4b"), 3.0))
            painter.drawArc(ring_rect, 90 * 16, -360 * 16)
            painter.setPen(QPen(QColor("#8a75ff"), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(ring_rect, 90 * 16, int(-360 * self._progress / 100 * 16))
        elif self._recording:
            painter.setPen(QPen(QColor("#f07883"), 2.4))
            painter.drawEllipse(ring_rect)

        center_x = self.width() / 2
        center_y = self.height() / 2
        icon_color = QColor("#ff8c98" if self._recording else "#E7E9EF")
        painter.setPen(QPen(icon_color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._recording:
            painter.drawRoundedRect(int(center_x - 6), int(center_y - 6), 12, 12, 2, 2)
        else:
            painter.drawRoundedRect(int(center_x - 4), int(center_y - 10), 8, 16, 4, 4)
            stem = QPainterPath()
            stem.moveTo(center_x - 9, center_y - 1)
            stem.quadTo(center_x - 9, center_y + 9, center_x, center_y + 9)
            stem.quadTo(center_x + 9, center_y + 9, center_x + 9, center_y - 1)
            painter.drawPath(stem)
            painter.drawLine(int(center_x), int(center_y + 9), int(center_x), int(center_y + 13))
            painter.drawLine(int(center_x - 5), int(center_y + 13), int(center_x + 5), int(center_y + 13))
        painter.end()
