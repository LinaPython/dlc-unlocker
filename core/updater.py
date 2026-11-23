# core/updater.py
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Callable

import requests

_REPO    = "LinaPython/dlc-unlocker"
_API_URL = f"https://api.github.com/repos/{_REPO}/releases/latest"
_VERSION_FILE = Path(__file__).resolve().parent.parent / "version.txt"


def versao_local() -> str:
    if _VERSION_FILE.exists():
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def checar_atualizacao(
    on_atualizado: Callable[[str, str, str], None],
    on_sem_atualizacao: Callable[[str], None] | None = None,
) -> None:
    """
    Checa em thread separada.
    on_atualizado(versao_nova, versao_local, url_release) — chamado se há update
    on_sem_atualizacao(versao_local)                      — chamado se está na última
    """
    threading.Thread(
        target=_checar,
        args=(on_atualizado, on_sem_atualizacao),
        daemon=True,
    ).start()


def _checar(
    on_atualizado: Callable,
    on_sem_atualizacao: Callable | None,
) -> None:
    try:
        resp = requests.get(_API_URL, timeout=8)
        resp.raise_for_status()
        data        = resp.json()
        tag         = data.get("tag_name", "").lstrip("v")
        url_release = data.get("html_url", f"https://github.com/{_REPO}/releases")
        local       = versao_local()

        if _maior(tag, local):
            on_atualizado(tag, local, url_release)
        elif on_sem_atualizacao:
            on_sem_atualizacao(local)

    except Exception:
        if on_sem_atualizacao:
            on_sem_atualizacao(versao_local())


def _maior(a: str, b: str) -> bool:
    """Retorna True se versão a > b. Compara tuplas de inteiros."""
    def parse(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return (0,)
    return parse(a) > parse(b)