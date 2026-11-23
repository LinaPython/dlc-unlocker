# core/config.py 
import json
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
PASTA_CONFIG  = _BASE_DIR / "configs"
ARQUIVO_CONFIG = PASTA_CONFIG / "config.json"
PASTA_PADRAO  = Path.home() / "Downloads" / "DLCs"


def carregar_config() -> dict:
    PASTA_CONFIG.mkdir(parents=True, exist_ok=True)
    if ARQUIVO_CONFIG.exists():
        try:
            with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
                dados = json.load(f)
            dados.setdefault("pasta_downloads", str(PASTA_PADRAO))
            return dados
        except (json.JSONDecodeError, OSError):
            pass
    return {"pasta_downloads": str(PASTA_PADRAO), "tema": "black"}


def salvar_config(config: dict) -> None:
    PASTA_CONFIG.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)