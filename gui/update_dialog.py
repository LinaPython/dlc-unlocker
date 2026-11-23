# gui/update_dialog.py 
from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox
)

from core.config import carregar_config, salvar_config


class UpdateDialog(QDialog):
    def __init__(
        self,
        versao_nova: str,
        versao_local: str,
        url_release: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Atualização disponível")
        self.setFixedSize(420, 220)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self._url = url_release

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        lbl_titulo = QLabel("Nova versão disponível")
        lbl_titulo.setObjectName("lbl_title")
        f = lbl_titulo.font()
        f.setPointSize(14)
        lbl_titulo.setFont(f)
        layout.addWidget(lbl_titulo)

        lbl_info = QLabel(
            f"Versão atual: <b>{versao_local}</b> &nbsp;→&nbsp; "
            f"Nova versão: <b>{versao_nova}</b>"
        )
        lbl_info.setTextFormat(Qt.TextFormat.RichText)
        lbl_info.setObjectName("lbl_muted")
        layout.addWidget(lbl_info)

        lbl_desc = QLabel("Acesse o GitHub para baixar a versão mais recente.")
        lbl_desc.setObjectName("lbl_muted")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        self.chk_ignorar = QCheckBox("Não mostrar novamente para esta versão")
        self.chk_ignorar.setObjectName("lbl_muted")
        layout.addWidget(self.chk_ignorar)

        layout.addStretch()

        btns = QHBoxLayout()
        btn_ver = QPushButton("Ver no GitHub")
        btn_ver.clicked.connect(self._abrir_github)
        btns.addWidget(btn_ver)

        btn_fechar = QPushButton("Agora não")
        btn_fechar.setObjectName("btn_theme")
        btn_fechar.clicked.connect(self._fechar)
        btns.addWidget(btn_fechar)

        layout.addLayout(btns)

    def _abrir_github(self) -> None:
        subprocess.Popen(["xdg-open", self._url])
        self._fechar()

    def _fechar(self) -> None:
        if self.chk_ignorar.isChecked():
            cfg = carregar_config()
            cfg["ignorar_versao"] = self._url
            salvar_config(cfg)
        self.accept()