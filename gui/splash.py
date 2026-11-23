# gui/splash.py 
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QApplication, QFrame
)

from core.config import carregar_config, salvar_config

_VERSION_FILE = Path(__file__).resolve().parent.parent / "version.txt"


def versao_atual() -> str:
    if _VERSION_FILE.exists():
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def deve_mostrar_splash() -> bool:
    cfg = carregar_config()
    return cfg.get("splash_visto", "") != versao_atual()


class SplashScreen(QWidget):
    def __init__(self, imagem: Path, texto: str) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(500, 520)
        self._center()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        frame = QFrame(self)
        frame.setObjectName("splash")
        frame.setFixedSize(500, 520)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(18)
        root.addWidget(frame)

        if imagem.exists():
            lbl_img = QLabel()
            px = QPixmap(str(imagem)).scaled(
                420, 420,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            lbl_img.setPixmap(px)
            lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_img.setObjectName("lbl_splash_img")
            layout.addWidget(lbl_img)

        lbl_txt = QLabel(texto)
        lbl_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_txt.setWordWrap(True)
        lbl_txt.setObjectName("lbl_muted")
        layout.addWidget(lbl_txt)

        btn = QPushButton("Entrar")
        btn.setFixedHeight(42)
        btn.clicked.connect(self._abrir_app)
        layout.addWidget(btn)

        self._app_aberta = False

    def _center(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )

    def _abrir_app(self) -> None:
        if self._app_aberta:
            return
        self._app_aberta = True
        cfg = carregar_config()
        cfg["splash_visto"] = versao_atual()
        salvar_config(cfg)
        from gui.app import MainWindow
        self._main = MainWindow()
        self._main.show()
        self.close()