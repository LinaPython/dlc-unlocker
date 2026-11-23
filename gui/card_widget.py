# gui/card_widget.py
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QProgressBar, QSizePolicy
)

from core.downloader import formatar_tamanho

_CACHE_DIR = Path(__file__).resolve().parent.parent / "configs" / "img_cache"

_TAG_ID: dict[str, str] = {
    "Expansion Pack": "tag_expansion",
    "KIT":            "tag_kit",
    "Free Pack":      "tag_free",
    "Game Pack":      "tag_game",
    "Stuff Pack":     "tag_stuff",
}


def _rounded_pixmap(px: QPixmap, radius: int = 10) -> QPixmap:
    """Recorta o pixmap com bordas arredondadas."""
    result = QPixmap(px.size())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, px.width(), px.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, px)
    painter.end()
    return result


def _fetch_image(url: str, cache_path: Path, callback: Callable[[QPixmap], None]) -> None:
    """Baixa imagem em thread separada, salva em cache, chama callback com QPixmap."""
    try:
        if cache_path.exists():
            px = QPixmap(str(cache_path))
            if not px.isNull():
                callback(px)
                return

        import requests as _req
        resp = _req.get(url,
                        timeout=10,
                        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"}
        )
        
        resp.raise_for_status()

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(resp.content)

        px = QPixmap()
        px.loadFromData(resp.content)
        if not px.isNull():
            callback(px)
    except Exception:
        pass 


class _ImageSignal(QObject):
    ready = Signal(QPixmap)


class CardArquivo(QFrame):
    sinal_update = Signal(dict)

    def __init__(
        self,
        item_id: str,
        item: dict,
        on_baixar: Callable[[str, dict], None],
        on_cancelar: Callable[[str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.item_id      = item_id
        self.item         = item
        self._on_baixar   = on_baixar
        self._on_cancelar = on_cancelar

        self.setFixedHeight(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        self._img_signal = _ImageSignal()
        self._img_signal.ready.connect(self._aplicar_imagem)

        tag_id = _TAG_ID.get(item.get("tag", ""), "tag_default")

        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(76, 76)
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setObjectName(tag_id)
        self.lbl_thumb.setText(item.get("tag", ""))
        self.lbl_thumb.setWordWrap(True)
        root.addWidget(self.lbl_thumb, 0, Qt.AlignmentFlag.AlignVCenter)

        img_url = item.get("imagem", "").strip()
        if img_url:
            safe = "".join(c if c.isalnum() else "_" for c in item_id)[:64]
            ext  = img_url.split(".")[-1].split("?")[0].lower()
            ext  = ext if ext in ("jpg", "jpeg", "png", "webp") else "jpg"
            cache_path = _CACHE_DIR / f"{safe}.{ext}"
            threading.Thread(
                target=_fetch_image,
                args=(img_url, cache_path, self._img_signal.ready.emit),
                daemon=True,
            ).start()

        centro = QVBoxLayout()
        centro.setSpacing(4)

        nome_row = QHBoxLayout()
        self.lbl_nome = QLabel(item.get("nome", ""))
        self.lbl_nome.setObjectName("lbl_card_nome")
        nome_row.addWidget(self.lbl_nome)

        self.lbl_tam = QLabel("")
        self.lbl_tam.setObjectName("lbl_muted")
        nome_row.addWidget(self.lbl_tam)
        nome_row.addStretch()
        centro.addLayout(nome_row)

        self.lbl_status = QLabel("Aguardando")
        self.lbl_status.setObjectName("lbl_muted")
        centro.addWidget(self.lbl_status)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setFixedHeight(6)
        self.bar.setTextVisible(False)
        centro.addWidget(self.bar)

        root.addLayout(centro, 1)

        btns = QVBoxLayout()
        btns.setSpacing(6)

        self.btn_baixar = QPushButton("Baixar")
        self.btn_baixar.setFixedWidth(100)
        self.btn_baixar.clicked.connect(self._clicar_baixar)
        btns.addWidget(self.btn_baixar)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setFixedWidth(100)
        self.btn_cancel.clicked.connect(self._clicar_cancelar)
        self.btn_cancel.hide()
        btns.addWidget(self.btn_cancel)
        btns.addStretch()

        root.addLayout(btns)
        self.sinal_update.connect(self._aplicar_update)

    def _aplicar_imagem(self, px: QPixmap) -> None:
        px = px.scaled(
            76, 76,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        if px.width() > 76 or px.height() > 76:
            x = (px.width()  - 76) // 2
            y = (px.height() - 76) // 2
            px = px.copy(x, y, 76, 76)
        px = _rounded_pixmap(px, radius=10)
        self.lbl_thumb.setPixmap(px)
        self.lbl_thumb.setText("")
        self.lbl_thumb.setObjectName("lbl_thumb")
        self.lbl_thumb.setStyleSheet("background: transparent; border: none;")

    def emitir_update(self, info: dict) -> None:
        self.sinal_update.emit(info)

    def _aplicar_update(self, info: dict) -> None:
        estado  = info["estado"]
        prog    = info["progresso"]
        vel     = info["velocidade"]
        nome    = info["nome"]
        total   = info.get("tamanho", 0)
        baixado = info.get("baixado", 0)
        v_txt   = f"{vel/1024:.1f} MB/s" if vel >= 1024 else f"{vel:.0f} KB/s"

        if estado == "resolvendo":
            self.lbl_status.setText("Resolvendo link...")

        elif estado == "iniciando":
            tam_txt = f"({formatar_tamanho(total)})" if total else ""
            self.lbl_tam.setText(tam_txt)
            self.lbl_status.setText("Conectando...")

        elif estado == "baixando":
            self.bar.setValue(int(prog * 1000))
            self.lbl_status.setText(
                f"Baixando  {prog*100:.1f}%  {formatar_tamanho(baixado)} / "
                f"{formatar_tamanho(total) if total else '?'}  {v_txt}"
            )

        elif estado == "concluido":
            self.bar.setValue(1000)
            self.lbl_status.setObjectName("lbl_status_ok")
            self.lbl_status.style().unpolish(self.lbl_status)
            self.lbl_status.style().polish(self.lbl_status)
            self.lbl_status.setText("Concluido")
            self.btn_baixar.setText("Concluido")
            self.btn_baixar.setEnabled(False)
            self.btn_cancel.hide()

        elif estado == "cancelado":
            self.bar.setValue(0)
            self.lbl_status.setText("Cancelado")
            self.btn_baixar.setText("Baixar")
            self.btn_baixar.setEnabled(True)
            self.btn_cancel.hide()
            self.btn_cancel.setEnabled(True)
            self.btn_cancel.setText("Cancelar")

        elif estado == "erro":
            self.lbl_status.setObjectName("lbl_status_err")
            self.lbl_status.style().unpolish(self.lbl_status)
            self.lbl_status.style().polish(self.lbl_status)
            self.lbl_status.setText(f"Erro: {nome}")
            self.btn_baixar.setText("Baixar")
            self.btn_baixar.setEnabled(True)
            self.btn_cancel.hide()

    def _clicar_baixar(self) -> None:
        self.btn_baixar.setEnabled(False)
        self.btn_baixar.setText("Baixando...")
        self.btn_cancel.show()
        self._on_baixar(self.item_id, self.item)

    def _clicar_cancelar(self) -> None:
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("Cancelando...")
        self._on_cancelar(self.item_id)