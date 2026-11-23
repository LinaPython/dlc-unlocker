# core/sims_finder.py
# agora verifca outros prefixos, preciso baixar o lutris pra entender como funciona.
import re
from pathlib import Path


def encontrar_sims() -> Path | None:
    home = Path.home()

    steam_roots = [
        home / ".local/share/Steam",
        home / ".steam/steam",
        home / "snap/steam/common/.local/share/Steam",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        home / ".var/app/com.valvesoftware.Steam/.steam/steam",
        home / ".var/app/com.valvesoftware.Steam/.steam/root",
    ]

    steamapps_dirs: list[Path] = []
    for root in steam_roots:
        sa = root / "steamapps"
        if sa.exists():
            steamapps_dirs.append(sa)
            vdf = sa / "libraryfolders.vdf"
            if vdf.exists():
                try:
                    txt = vdf.read_text(encoding="utf-8", errors="ignore")
                    for p in re.findall(r'"path"\s+"([^"]+)"', txt):
                        extra = Path(p) / "steamapps"
                        if extra.exists() and extra not in steamapps_dirs:
                            steamapps_dirs.append(extra)
                except OSError:
                    pass

    for sa in steamapps_dirs:
        sims = sa / "common" / "The Sims 4"
        if sims.exists() and (sims / "Game").exists():
            return sims

    for sa in steamapps_dirs:
        sims = sa / "common" / "The Sims 4"
        if sims.exists():
            return sims

    return None