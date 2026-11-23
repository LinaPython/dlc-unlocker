# core/catalog.py 
import json
import requests
from pathlib import Path

_BASE_DIR    = Path(__file__).resolve().parent.parent
_PASTA_CONFIG = _BASE_DIR / "configs"
_CATALOG_URL  = (
    "https://raw.githubusercontent.com/LinaPython/"
    "dlc-unlocker-data/refs/heads/main/catalog.json"
)


def carregar_catalogo() -> list[dict]:
    cache = _PASTA_CONFIG / "catalog_cache.json"
    try:
        resp = requests.get(_CATALOG_URL, timeout=10)
        resp.raise_for_status()
        dados: list[dict] = resp.json()
        _PASTA_CONFIG.mkdir(parents=True, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        return dados
    except Exception:
        if cache.exists():
            with open(cache, "r", encoding="utf-8") as f:
                return json.load(f)
        return []