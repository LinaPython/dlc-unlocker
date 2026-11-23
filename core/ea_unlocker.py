import os
import re
import glob
import shutil
import datetime
import subprocess
import platform
from pathlib import Path


class EAUnlocker:
    def __init__(self):
        self.home = Path.home()
        self.client = "ea_app"
        self.dll_name = "version.dll"
        self.main_config = "config.ini"
        self.game_config = "g_TS4.ini"
        self.users_dir = "drive_c/users"
        self.ea_app_parent = "drive_c/Program Files/Electronic Arts/EA Desktop"
        self.unlocker_dir_base = "LinaMod/In DLC LinaSync v3/"

        self.prefix_path = None
        self.prefix_name = ""
        self.prefix_config = ""
        self.prefix_user = ""
        self.prefix_ea_app = ""

        self.all_prefix_paths = []
        self.all_prefix_names = []
        self.all_prefix_configs = []
        self.all_prefix_users = []
        self.all_prefix_ea_apps = []

        self.reg_path = None
        self.dst_dll = None
        self.dst_dll2 = None
        self.configs_dir = None
        self.logs_dir = None
        self.dst_config = None

        self.known_ids = {
            "1222670": "The Sims 4"
        }

    def _warn(self, msg):
        print(f"\033[31m{msg}\033[0m")

    def _fail(self, msg):
        print(f"\033[37;41mFatal error:\033[0m \033[31m{msg}\033[0m")
        raise RuntimeError(msg)

    def _success(self, msg):
        print(f"\033[32m{msg}\033[0m")

    def _find_ea_app(self, prefix_path, stage=""):
        base = prefix_path / self.ea_app_parent
        if stage:
            base = base / stage
        if not base.exists():
            return None
        direct_path = base / "EA Desktop"
        if direct_path.exists():
            return str(direct_path)
        try:
            for candidate in base.iterdir():
                if candidate.is_dir():
                    ea_folder = candidate / "EA Desktop"
                    if ea_folder.exists():
                        return str(ea_folder)
        except PermissionError:
            pass
        return None

    def _get_prefix_name(self, appid, steamapps_path):
        prefix_name = f"Unknown prefix ({appid})"
        prefix_config = ""
        if appid in self.known_ids:
            name = self.known_ids[appid]
            return name, name
        manifest = steamapps_path / f"appmanifest_{appid}.acf"
        if manifest.exists():
            try:
                content = manifest.read_text(encoding='utf-8', errors='ignore')
                match = re.search(r'"name"\s+"([^"]+)"', content)
                if match:
                    prefix_name = match.group(1)
            except Exception:
                pass
        return prefix_name, prefix_config

    def _check_prefix(self, path, name, src, steamapps_path=None):
        path = Path(path)
        ea_app_path = self._find_ea_app(path)
        if not ea_app_path:
            return
        config = ""
        usr = os.environ.get("USER", "user")
        if src == "steam":
            appid = name
            p_name, p_config = self._get_prefix_name(appid, steamapps_path)
            name = f"{p_name} (Steam)"
            config = p_config
            usr = "steamuser"
        elif src != "wine":
            name = f"{name} ({src})"
        self.all_prefix_paths.append(str(path))
        self.all_prefix_names.append(name)
        self.all_prefix_configs.append(config)
        self.all_prefix_users.append(usr)
        self.all_prefix_ea_apps.append(ea_app_path)

    def get_wine_prefix(self):
        wineprefix = os.environ.get("WINEPREFIX")
        if not wineprefix:
            wineprefix = self.home / ".wine"
            name = "Default Wine prefix"
        else:
            name = "Custom Wine prefix"
        self._check_prefix(wineprefix, name, "wine")

    def get_lutris_prefixes(self):
        lutris_path = self.home / "Games"
        if not lutris_path.exists():
            return
        for prefix in lutris_path.iterdir():
            if prefix.is_dir():
                self._check_prefix(prefix, prefix.name, "Lutris")

    def get_bottles_prefixes(self):
        bottles_paths = [
            self.home / ".var/app/com.usebottles.bottles/data/bottles/bottles",
            self.home / ".local/share/bottles"
        ]
        for b_path in bottles_paths:
            if b_path.exists():
                for prefix in b_path.iterdir():
                    if prefix.is_dir():
                        self._check_prefix(prefix, prefix.name, "Bottles")

    def get_steam_prefixes(self):
        steam_paths = [
            self.home / ".steam/steam",
            self.home / ".local/share/Steam",
            self.home / "snap/steam/common/.local/share/Steam",
            self.home / "steam/root",
            self.home / "steam",
            self.home / ".var/app/com.valvesoftware.Steam/.steam/steam",
            self.home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
            self.home / ".var/app/com.valvesoftware.Steam/.steam/root",
            self.home / ".var/app/com.valvesoftware.Steam/.steam",
        ]
        steamapps_path = None
        for sp in steam_paths:
            tmp = sp / "steamapps"
            if tmp.exists():
                steamapps_path = tmp
                break
        if not steamapps_path:
            return
        library_vdf = steamapps_path / "libraryfolders.vdf"
        if not library_vdf.exists():
            return
        try:
            content = library_vdf.read_text(encoding='utf-8', errors='ignore')
            paths = re.findall(r'"path"\s+"([^"]+)"', content)
            for library_path in paths:
                lib_steamapps = Path(library_path) / "steamapps"
                compatdata = lib_steamapps / "compatdata"
                if compatdata.exists():
                    for prefix_dir in compatdata.iterdir():
                        if prefix_dir.is_dir() and prefix_dir.name.isdigit():
                            pfx_path = prefix_dir / "pfx"
                            self._check_prefix(pfx_path, prefix_dir.name, "steam", lib_steamapps)
        except Exception as e:
            print(f"Erro ao ler libraryfolders.vdf: {e}")

    def discover_prefixes(self):
        self.all_prefix_paths = []
        self.all_prefix_names = []
        self.all_prefix_configs = []
        self.all_prefix_users = []
        self.all_prefix_ea_apps = []

        self.get_wine_prefix()
        self.get_lutris_prefixes()
        self.get_bottles_prefixes()
        self.get_steam_prefixes()

        if not self.all_prefix_paths:
            self._fail("No prefixes found. Run the game once and then try again.")

    def select_prefix(self, index=0):
        if index < 0 or index >= len(self.all_prefix_paths):
            self._fail("Invalid prefix index")

        self.prefix_path    = Path(self.all_prefix_paths[index])
        self.prefix_name    = self.all_prefix_names[index]
        self.prefix_config  = self.all_prefix_configs[index]
        self.prefix_user    = self.all_prefix_users[index]
        self.prefix_ea_app  = self.all_prefix_ea_apps[index]

        staged_ea_app = self._find_ea_app(self.prefix_path, "StagedEADesktop")

        self.reg_path  = self.prefix_path / "user.reg"
        self.dst_dll   = Path(self.prefix_ea_app) / self.dll_name
        self.dst_dll2  = Path(staged_ea_app) / self.dll_name if staged_ea_app else None

        appdata_rel      = f"AppData/Roaming/{self.unlocker_dir_base}"
        localappdata_rel = f"AppData/Local/{self.unlocker_dir_base}"

        self.configs_dir = self.prefix_path / self.users_dir / self.prefix_user / appdata_rel
        self.logs_dir    = self.prefix_path / self.users_dir / self.prefix_user / localappdata_rel
        self.dst_config  = self.configs_dir / self.main_config

    def install_unlocker(self):
        """Instala version.dll, config.ini e g_TS4.ini no prefixo selecionado."""
        base_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        src_dll        = base_dir / self.client / self.dll_name
        src_config     = base_dir / self.main_config
        src_game_cfg   = base_dir / self.game_config

        if not src_dll.exists():
            self._fail(f"{src_dll} não encontrado. Extraia todos os arquivos.")
        if not src_config.exists():
            self._fail(f"{src_config} não encontrado. Extraia todos os arquivos.")
        if not src_game_cfg.exists():
            self._fail(f"{src_game_cfg} não encontrado. Extraia todos os arquivos.")

        self.configs_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(src_config,   self.dst_config)
        self._success("config.ini copiado!")

        shutil.copy2(src_game_cfg, self.configs_dir / self.game_config)
        self._success("g_TS4.ini copiado!")

        timestamp = int(datetime.datetime.now().timestamp())
        reg_content = (
            f"\n[Software\\\\Wine\\\\DllOverrides] {timestamp}\n"
            f"\"version\"=\"native,builtin\"\n"
        )
        with open(self.reg_path, "a") as f:
            f.write(reg_content)

        shutil.copy2(src_dll, self.dst_dll)
        self._success("version.dll instalado!")

        if self.dst_dll2:
            try:
                shutil.copy2(src_dll, self.dst_dll2)
                self._success("version.dll instalado no StagedEADesktop também!")
            except Exception:
                pass

    def uninstall_unlocker(self):
        if self.configs_dir.exists():
            shutil.rmtree(self.configs_dir)
            self._success("Pasta de configs removida!")
            try:
                os.rmdir(self.configs_dir.parent)
            except OSError:
                pass

        if self.logs_dir.exists():
            shutil.rmtree(self.logs_dir)
            self._success("Pasta de logs removida!")
            try:
                os.rmdir(self.logs_dir.parent)
            except OSError:
                pass

        if self.dst_dll and self.dst_dll.exists():
            self.dst_dll.unlink()
            self._success("version.dll removido!")

        if self.dst_dll2 and self.dst_dll2.exists():
            self.dst_dll2.unlink()

    def open_configs_folder(self):
        if self.configs_dir.exists():
            self._open_file_explorer(self.configs_dir)
            self._success("Pasta de configs aberta!")
        else:
            self._warn("Pasta de configs não encontrada. Instale o Unlocker primeiro.")

    def open_logs_folder(self):
        if self.logs_dir.exists():
            self._open_file_explorer(self.logs_dir)
            self._success("Pasta de logs aberta!")
        else:
            self._warn("Pasta de logs não encontrada. Instale o Unlocker e execute o jogo primeiro.")

    def _open_file_explorer(self, path):
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])