# gui/bg_window.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QMainWindow


class BgWindow(QMainWindow):
    """
    QMainWindow que pinta uma imagem de fundo escalonada uma unica vez.
    Usada pelos temas que precisam de imagem — carrega e redimensiona
    no resize, nao em cada repaint de widget filho.
    """
    _bg_cache: dict[str, QPixmap] = {}

    def __init__(self, bg_path: str | None = None) -> None:
        super().__init__()
        self._bg_pixmap: QPixmap | None = None
        self._bg_scaled: QPixmap | None = None
        if bg_path:
            self.set_background(bg_path)

    def set_background(self, path: str) -> None:
        if path not in BgWindow._bg_cache:
            px = QPixmap(path)
            if not px.isNull():
                BgWindow._bg_cache[path] = px.scaled(
                    1920, 1080,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
        self._bg_pixmap = BgWindow._bg_cache.get(path)
        self._bg_scaled = None 
        self.update()

    def clear_background(self) -> None:
        self._bg_pixmap = None
        self._bg_scaled = None
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._bg_pixmap:
            self._bg_scaled = self._bg_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )

    def paintEvent(self, event) -> None:
        if self._bg_scaled:
            painter = QPainter(self)
            x = (self.width()  - self._bg_scaled.width())  // 2
            y = (self.height() - self._bg_scaled.height()) // 2
            painter.drawPixmap(x, y, self._bg_scaled)
            painter.end()
        else:
            super().paintEvent(event)