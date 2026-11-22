from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QPushButton

from ui.theme import app_icon


class CircularMicButton(QPushButton):
    """Centered Material microphone icon with optional recording/download rings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._progress: int | None = None
        self._recording = False
        self.setFixedSize(40, 40)
        self.setIcon(app_icon("mdi6.microphone", "#E7E9EF"))
        self.setIconSize(QSize(17, 17))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setToolTip("Record voice")

    def set_download_progress(self, value: int | None) -> None:
        self._progress = None if value is None else max(0, min(100, int(value)))
        self.update()

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        self.setIcon(
            app_icon("mdi6.microphone", "#FF8C98" if recording else "#E7E9EF")
        )
        self.setToolTip("Stop recording" if recording else "Record voice")
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring_rect = self.rect().adjusted(2, 2, -2, -2)

        if self._progress is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#20242B"))
            painter.drawEllipse(ring_rect)
            painter.setPen(QPen(QColor("#343C4B"), 2.2))
            painter.drawArc(ring_rect, 90 * 16, -360 * 16)
            painter.setPen(
                QPen(
                    QColor("#8A75FF"),
                    2.2,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawArc(
                ring_rect, 90 * 16, int(-360 * self._progress / 100 * 16)
            )
        elif self._recording:
            painter.setPen(QPen(QColor("#F07883"), 2.2))
            painter.setBrush(QColor("#29233D"))
            painter.drawEllipse(ring_rect)
        elif self.underMouse():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#292E37"))
            painter.drawEllipse(ring_rect)

        mode = QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled
        state = QIcon.State.On if self._recording else QIcon.State.Off
        self.icon().paint(
            painter,
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            mode,
            state,
        )
        painter.end()
