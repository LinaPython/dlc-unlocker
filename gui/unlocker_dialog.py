# gui/unlocker_dialog.py 
from __future__ import annotations

import threading

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton
)

from core.ea_unlocker import EAUnlocker


class _Sinais(QObject):
    status = Signal(str)
    prefixes_prontos = Signal(list)


class UnlockerDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("EA Unlocker Manager")
        self.setFixedSize(500, 320)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self._unlocker = EAUnlocker()
        self._sinais   = _Sinais()
        self._sinais.status.connect(self._set_status)
        self._sinais.prefixes_prontos.connect(self._popular_prefixes)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        self.lbl_status = QLabel("Inicializando…")
        self.lbl_status.setObjectName("lbl_muted")
        layout.addWidget(self.lbl_status)

        self.combo = QComboBox()
        layout.addWidget(self.combo)

        btns = QHBoxLayout()
        self.btn_install = QPushButton("Instalar / Atualizar")
        self.btn_install.clicked.connect(self._install)
        btns.addWidget(self.btn_install)

        self.btn_uninstall = QPushButton("Desinstalar")
        self.btn_uninstall.setObjectName("btn_danger")
        self.btn_uninstall.clicked.connect(self._uninstall)
        btns.addWidget(self.btn_uninstall)

        self.btn_configs = QPushButton("Abrir Configs")
        self.btn_configs.setObjectName("btn_info")
        self.btn_configs.clicked.connect(self._open_configs)
        btns.addWidget(self.btn_configs)

        layout.addLayout(btns)
        layout.addStretch()

        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self) -> None:
        try:
            self._unlocker.discover_prefixes()
            names = self._unlocker.all_prefix_names
            self._sinais.prefixes_prontos.emit(names)
        except Exception as e:
            self._sinais.status.emit(f"Erro: {e}")

    def _do(self, acao: str) -> None:
        try:
            idx = self.combo.currentIndex()
            self._unlocker.select_prefix(idx)
            if acao == "install":
                self._unlocker.install_unlocker()
                self._sinais.status.emit("Instalação concluída!")
            else:
                self._unlocker.uninstall_unlocker()
                self._sinais.status.emit("Desinstalação concluída.")
        except Exception as e:
            self._sinais.status.emit(f"Falha: {e}")

    def _popular_prefixes(self, names: list[str]) -> None:
        if not names:
            self.lbl_status.setText("Nenhum prefixo encontrado.")
            return
        self.combo.addItems(names)
        self.lbl_status.setText(f"{len(names)} prefixo(s) encontrado(s).")

    def _set_status(self, msg: str) -> None:
        self.lbl_status.setText(msg)

    def _install(self) -> None:
        threading.Thread(target=self._do, args=("install",), daemon=True).start()

    def _uninstall(self) -> None:
        threading.Thread(target=self._do, args=("uninstall",), daemon=True).start()

    def _open_configs(self) -> None:
        try:
            idx = self.combo.currentIndex()
            self._unlocker.select_prefix(idx)
            self._unlocker.open_configs_folder()
        except Exception as e:
            self.lbl_status.setText(f"Erro: {e}")