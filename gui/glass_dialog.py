# gui/glass_dialog.py 
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QGraphicsBlurEffect, QWidget


class GlassDialog(QDialog):
    """
    Base
    """
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(0)   


    def _aplicar_blur_fundo(self, raio: int = 8) -> None:
        """Chame no __init__ do filho se quiser blur no conteudo interno."""
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(raio)
        if self.children():
            widget = self.children()[0]
            if isinstance(widget, QWidget):
                widget.setGraphicsEffect(blur)