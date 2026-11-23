# core/logger.py
import logging
from pathlib import Path
from datetime import datetime

_BASE_DIR = Path(__file__).resolve().parent.parent
_PASTA_LOGS = _BASE_DIR / "logs"

def _setup() -> logging.Logger:
    _PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("dlc_unlocker")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(
        _PASTA_LOGS / "dlc_unlocker.log", encoding="utf-8"
    )
    fh.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s — %(message)s",
                          datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(fh)
    return logger

log = _setup()

def escrever_log(mensagem: str) -> None:
    log.info(mensagem)