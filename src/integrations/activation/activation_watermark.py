#!/usr/bin/env python3
"""
GeminiOS Desktop Activation Watermark (`activation_watermark.py`)
Displays a semi-transparent, click-through watermark in the bottom-right corner:
    Активация GeminiOS
    Чтобы активировать GeminiOS, перейдите в «Параметры».
Disappears permanently once activated via `gem activate` or Gemini Spotlight.
"""

import os
import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QApplication, QWidget

GLOBAL_ACT_FILE = Path("/etc/geminios-activated")
USER_ACT_FILE = Path.home() / ".config/geminios-activated"


def is_activated() -> bool:
    return GLOBAL_ACT_FILE.exists() or USER_ACT_FILE.exists()


class ActivationWatermark(QWidget):
    def __init__(self):
        super().__init__()
        # Translucent, stay on top, click-through overlay that bypasses WM placement rules
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.BypassWindowManagerHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.setFixedSize(360, 80)
        self._position_on_screen()

        # Keep pinned to bottom-right if screen geometry or workarea changes
        primary = QApplication.primaryScreen()
        if primary:
            primary.availableGeometryChanged.connect(lambda _: self._position_on_screen())
            primary.geometryChanged.connect(lambda _: self._position_on_screen())

        # Watch for activation status changes
        self.check_timer = QTimer(self)
        self.check_timer.setInterval(3000)
        self.check_timer.timeout.connect(self._check_status)
        self.check_timer.start()

    def _position_on_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        # Pin strictly to the bottom-right corner (24px right margin, 32px bottom margin above panel)
        x = geo.x() + geo.width() - self.width() - 24
        y = geo.y() + geo.height() - self.height() - 32
        self.setGeometry(x, y, self.width(), self.height())

    def showEvent(self, event):
        super().showEvent(event)
        self._position_on_screen()
        QTimer.singleShot(100, self._position_on_screen)
        QTimer.singleShot(500, self._position_on_screen)

    def _check_status(self):
        if is_activated():
            self.close()
            sys.exit(0)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Draw Title
        title_font = QFont("Roboto", 13, QFont.Weight.Medium)
        painter.setFont(title_font)
        painter.setPen(QColor(230, 230, 235, 125))
        painter.drawText(10, 26, "Активация GeminiOS")

        # Draw Subtitle
        sub_font = QFont("Roboto", 10, QFont.Weight.Normal)
        painter.setFont(sub_font)
        painter.setPen(QColor(200, 200, 210, 105))
        painter.drawText(10, 48, "Чтобы активировать GeminiOS, перейдите в «Параметры»")
        painter.drawText(10, 66, "или введите `gem activate` в терминале.")


def main() -> int:
    if is_activated():
        return 0

    app = QApplication(sys.argv)
    w = ActivationWatermark()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
