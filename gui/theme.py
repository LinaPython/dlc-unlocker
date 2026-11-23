# gui/theme.py
from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import QApplication

_BASE = Path(__file__).resolve().parent / "styles"
_current = "dark"


def available() -> list[str]:
    """Retorna todos os temas disponíveis (arquivos .qss em gui/styles/)."""
    return sorted(p.stem for p in _BASE.glob("*.qss"))


def apply(app: QApplication, name: str = "dark") -> None:
    global _current
    qss = _BASE / f"{name}.qss"
    if not qss.exists():
        return
    app.setStyleSheet(qss.read_text(encoding="utf-8"))
    _current = name


def current() -> str:
    return _current