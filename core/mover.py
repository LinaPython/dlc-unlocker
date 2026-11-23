# core/mover.py 
import re
import shutil
from pathlib import Path
from typing import Callable


_PAD = re.compile(r'^(EP|GP|SP|FP|KT)\d+', re.IGNORECASE)


def mover_dlcs(
    pasta_dl: Path,
    sims: Path,
    on_progress: Callable[[str, int, int], None],
    on_confirmar_substituicao: Callable[[str, str], bool],
    on_log: Callable[[str], None],
) -> tuple[list[str], list[str]]:
    """
    Move pastas extraídas para o diretório correto do Sims 4.
    Retorna (pulados, erros).
    """
    pastas = [
        p for p in pasta_dl.iterdir()
        if p.is_dir() and re.match(r'Sims4_DLC_', p.name, re.IGNORECASE)
    ]
    total = len(pastas)
    erros: list[str] = []
    pulados: list[str] = []

    dst_r = sims
    dst_d = sims / "__Installer" / "DLC"

    for i, pasta in enumerate(pastas):
        nome = pasta.name
        on_progress(nome, i, total)

        raiz = next(
            (p for p in pasta.iterdir() if p.is_dir() and _PAD.match(p.name)),
            None,
        )
        dlc_dir = None
        inst = pasta / "__Installer" / "DLC"
        if inst.exists():
            dlc_dir = next(
                (p for p in inst.iterdir() if p.is_dir() and _PAD.match(p.name)),
                None,
            )

        for src, base, label in [
            (raiz, dst_r, "raiz"),
            (dlc_dir, dst_d, "__Installer/DLC"),
        ]:
            if src is None:
                continue
            dst = base / src.name
            if dst.exists():
                if not on_confirmar_substituicao(src.name, label):
                    pulados.append(f"{src.name} em {label}")
                    continue
                shutil.rmtree(dst)
            try:
                base.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                on_log(f"✔ Movido: {src.name} → {label}")
            except Exception as e:
                erros.append(f"{src.name}: {e}")

    return pulados, erros