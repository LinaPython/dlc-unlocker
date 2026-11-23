# gui/progress_dialog.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar
)
from gui.glass_dialog import GlassDialog


class ProgressDialog(GlassDialog):
    def __init__(self, titulo: str, subtitulo: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setFixedSize(540, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(10)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setObjectName("lbl_title")
        layout.addWidget(lbl_titulo)

        lbl_sub = QLabel(subtitulo)
        lbl_sub.setObjectName("lbl_muted")
        layout.addWidget(lbl_sub)

        g_row = QHBoxLayout()
        self.lbl_g = QLabel("Aguardando...")
        self.lbl_g.setObjectName("lbl_muted")
        g_row.addWidget(self.lbl_g)
        self.lbl_c = QLabel("0 / 0")
        self.lbl_c.setObjectName("lbl_muted")
        self.lbl_c.setAlignment(Qt.AlignmentFlag.AlignRight)
        g_row.addWidget(self.lbl_c)
        layout.addLayout(g_row)

        self.bar_g = QProgressBar()
        self.bar_g.setRange(0, 1000)
        self.bar_g.setValue(0)
        self.bar_g.setFixedHeight(6)
        self.bar_g.setTextVisible(False)
        layout.addWidget(self.bar_g)

        self.lbl_a = QLabel("")
        self.lbl_a.setObjectName("lbl_muted")
        layout.addWidget(self.lbl_a)

        self.bar_a = QProgressBar()
        self.bar_a.setObjectName("bar_success")
        self.bar_a.setRange(0, 1000)
        self.bar_a.setValue(0)
        self.bar_a.setFixedHeight(6)
        self.bar_a.setTextVisible(False)
        layout.addWidget(self.bar_a)

        self.lbl_d = QLabel("")
        self.lbl_d.setObjectName("lbl_muted")
        layout.addWidget(self.lbl_d)

        layout.addStretch()

    def atualizar(
        self,
        g_txt: str,
        c_txt: str,
        g_pct: float,
        a_txt: str,
        a_pct: float,
        d_txt: str = "",
    ) -> None:
        self.lbl_g.setText(g_txt)
        self.lbl_c.setText(c_txt)
        self.bar_g.setValue(int(g_pct * 1000))
        self.lbl_a.setText(a_txt)
        self.bar_a.setValue(int(a_pct * 1000))
        self.lbl_d.setText(d_txt)