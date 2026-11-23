# gui/smooth_scroll.py 
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QScrollArea, QWidget


class SmoothScrollArea(QScrollArea):
    """
    QScrollArea com inércia no scroll vertical.
    Velocidade decai exponencialmente após soltar o mouse.
    """
    _FRICTION   = 0.82   # quanto da velocidade sobra por tick
    _TICK_MS    = 16     # ~60fps
    _MIN_SPEED  = 0.5    # px/tick abaixo disso para

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._velocity = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(self._TICK_MS)
        self._timer.timeout.connect(self._tick)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        self._velocity -= delta * 0.4
        if not self._timer.isActive():
            self._timer.start()
        event.accept()

    def _tick(self) -> None:
        if abs(self._velocity) < self._MIN_SPEED:
            self._velocity = 0.0
            self._timer.stop()
            return
        bar = self.verticalScrollBar()
        new_val = bar.value() + int(self._velocity)
        new_val = max(bar.minimum(), min(bar.maximum(), new_val))
        bar.setValue(new_val)
        self._velocity *= self._FRICTION