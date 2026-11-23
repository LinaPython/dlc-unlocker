#core/extractor.py
import zipfile
from pathlib import Path
from typing import Callable


def extrair_zips(
    pasta: Path,
    on_progress: Callable[[str, int, int, str, int, int, int, int], None],
    on_erro: Callable[[str], None],
) -> tuple[int, list[str]]:
    """
    Extrai todos os .zip em `pasta`.
    on_progress(nome, i, total, membro, j, total_membros, i_global, total_global)
    Retorna (n_ok, lista_erros).
    """
    zips = list(pasta.glob("*.zip"))
    total = len(zips)
    erros: list[str] = []

    for i, zp in enumerate(zips):
        nome = zp.stem
        dest = zp.parent / nome
        try:
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zp, "r") as zf:
                membros = zf.infolist()
                tm = len(membros)
                for j, m in enumerate(membros):
                    zf.extract(m, dest)
                    on_progress(nome, i, total, m.filename, j + 1, tm)
        except zipfile.BadZipFile:
            erros.append(f"{nome}: zip corrompido")
            on_erro(f"{nome}: zip corrompido")
        except Exception as e:
            erros.append(f"{nome}: {e}")
            on_erro(f"{nome}: {e}")

    return total - len(erros), erros