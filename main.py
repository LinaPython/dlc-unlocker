import os
import re
import sys
import json
import time
import threading
import zipfile
import requests
import shutil
import subprocess
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
try:
    from curl_cffi import requests as cffi_requests
    _CFFI_OK = True
except ImportError:
    _CFFI_OK = False
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, filedialog

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(BASE_DIR / "core"))

import customtkinter as ctk
from splash import SplashScreen        # type: ignore[import]
from ea_unlocker import EAUnlocker     # type: ignore[import]


# DADOS
ARQUIVOS: list[dict] = []
CORES_TAG      = {"Expansion Pack": "#98008E", "KIT": "#FF0000", "Free Pack": "#008000", "Game Pack": "#0000FF", "Stuff Pack": "#FFA500"}
COR_TAG_PADRAO = "#5A5A5A"

# CONFIGURAÇÃO
PASTA_CONFIG   = BASE_DIR / "configs"
ARQUIVO_CONFIG = PASTA_CONFIG / "config.json"
PASTA_LOGS     = BASE_DIR / "logs"
PASTA_PADRAO   = os.path.expanduser("~/Downloads/DLCs")


def carregar_config():
    PASTA_CONFIG.mkdir(parents=True, exist_ok=True)
    PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    if ARQUIVO_CONFIG.exists():
        try:
            with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
                dados = json.load(f)
                dados.setdefault("pasta_downloads", PASTA_PADRAO)
                return dados
        except (json.JSONDecodeError, OSError):
            pass
    return {"pasta_downloads": PASTA_PADRAO}


def salvar_config(config):
    PASTA_CONFIG.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def escrever_log(mensagem):
    PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    with open(PASTA_LOGS / "dlc_unlocker.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensagem}\n")

CATALOG_URL = "https://raw.githubusercontent.com/LinaPython/dlc-unlocker-data/refs/heads/main/catalog.json"


def carregar_catalogo() -> list[dict]:
    """Busca o catálogo remoto. Fallback para cache local se offline."""
    cache = PASTA_CONFIG / "catalog_cache.json"
    try:
        resp = requests.get(CATALOG_URL, timeout=10)
        resp.raise_for_status()
        dados = resp.json()
        PASTA_CONFIG.mkdir(parents=True, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        return dados
    except Exception:
        if cache.exists():
            with open(cache, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
def formatar_tamanho(bytes_: int) -> str:
    if bytes_ <= 0:
        return "? MB"
    valor = float(bytes_)
    for unidade in ("B", "KB", "MB", "GB"):
        if valor < 1024:
            return f"{valor:.1f} {unidade}"
        valor /= 1024
    return f"{valor:.1f} TB"


# HTTP — sessão compartilhada com pool e retries
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


def _nova_sessao(pool: int = 8) -> requests.Session:
    s = requests.Session()
    r = Retry(total=3, backoff_factor=0.5,
               status_forcelist=[429, 500, 502, 503, 504],
               allowed_methods=["GET", "HEAD"])
    a = HTTPAdapter(pool_connections=pool, pool_maxsize=pool, max_retries=r)
    s.mount("https://", a)
    s.mount("http://",  a)
    return s


_SESSAO_PAGE = _nova_sessao(pool=4)
_SESSAO_PAGE.headers.update({
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
})



# MEDIAFIRE — resolve link direto e tamanho
_CDN_RE = re.compile(r'https://download\d+\.mediafire\.com/[^\s"\'<>]+')


def _extrair_link_cdn(html: str) -> str | None:
    """Scan bruto no HTML — pega qualquer link download\\d+.mediafire.com."""
    # Cloudflare pode entregar o link com HTML entities (&amp; etc.)
    from html import unescape
    html_limpo = unescape(html)
    m = _CDN_RE.search(html_limpo)
    return m.group(0).rstrip("\"'\\&") if m else None


def _get_pagina(url: str) -> tuple[str, object]:
    """
    Busca a página do Mediafire contornando o Cloudflare.
    Usa curl_cffi (impersonation de browser) se disponível,
    senão cai no requests normal.
    Retorna (html, sessao_para_download).
    """
    if _CFFI_OK:
        sessao = cffi_requests.Session(impersonate="chrome120")
        # Cloudflare emite cf_clearance com delay — tenta até 3x com espera crescente
        for tentativa, espera in enumerate([0, 3, 6], start=1):
            if espera:
                time.sleep(espera)
            resp = sessao.get(url, timeout=20, allow_redirects=True)
            if resp.status_code != 403:
                return resp.text, sessao
        raise ValueError(
            f"Cloudflare bloqueou após 3 tentativas (403): {url}"
        )
    else:
        sessao = _nova_sessao(pool=4)
        sessao.headers.update({
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        resp = sessao.get(url, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        return resp.text, sessao


def resolver_mediafire(url_pagina: str) -> tuple[str, str, int, object]:
    """
    Retorna (url_direta, nome_arquivo, tamanho_bytes, sessao).
    Usa curl_cffi para contornar o Cloudflare challenge que bloqueia
    requests puro em alguns arquivos do Mediafire.
    """
    html, sessao = _get_pagina(url_pagina)
    link = _extrair_link_cdn(html)

    if not link:
        raise ValueError(
            f"Link CDN não encontrado: {url_pagina}\n"
            "Instale curl_cffi para contornar o Cloudflare: pip install curl-cffi"
        )

    nome    = requests.utils.unquote(link.split("/")[-1].split("?")[0])
    tamanho = 0

    m = re.search(r'\(([\d.,]+)\s*(KB|MB|GB)\)', html, re.IGNORECASE)
    if m:
        val  = float(m.group(1).replace(",", "."))
        mult = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}[m.group(2).upper()]
        tamanho = int(val * mult)

    return link, nome, tamanho, sessao


# GERENCIADOR DE DOWNLOADS
class GerenciadorDownloads:
    CHUNK = 4 * 1024 * 1024  # 4 MB — chunk grande reduz overhead do GIL

    def __init__(self, pasta_downloads, log=print):
        self.pasta_downloads = pasta_downloads
        self.log             = log
        self.handles         = {}
        self._cancelados     = set()
        self._sessao_dl      = _nova_sessao(pool=10)
        self._sessao_dl.headers.update({"User-Agent": _UA})

    def atualizar_pasta(self, nova):
        self.pasta_downloads = nova

    def iniciar(self, item_id, url, on_update):
        self.handles[item_id] = True
        threading.Thread(target=self._baixar,
                         args=(item_id, url, on_update),
                         daemon=True).start()

    def _baixar(self, item_id, url, on_update):
        os.makedirs(self.pasta_downloads, exist_ok=True)
        try:
            on_update({"estado": "resolvendo", "progresso": 0,
                       "velocidade": 0, "nome": "", "tamanho": 0})

            url_dl, nome, tam_pag, sessao_dl = resolver_mediafire(url)
            destino = os.path.join(self.pasta_downloads, nome)

            _headers_dl = {
                "Referer":        url,
                "Origin":         "https://www.mediafire.com",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
            }

            # curl_cffi Response não suporta context manager — usa sem `with` 
            resp = sessao_dl.get(url_dl, stream=True, timeout=30, headers=_headers_dl)
            resp.raise_for_status()
            total   = int(resp.headers.get("Content-Length", 0)) or tam_pag
            baixado = 0
            t0      = time.time()
            t_ui    = t0

            on_update({"estado": "iniciando", "progresso": 0,
                       "velocidade": 0, "nome": nome, "tamanho": total})

            try:
                with open(destino, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=self.CHUNK):
                        if not chunk:
                            continue
                        if item_id in self._cancelados:
                            self._cancelados.discard(item_id)
                            self.handles.pop(item_id, None)
                            on_update({"estado": "cancelado", "progresso": 0,
                                       "velocidade": 0, "nome": nome,
                                       "tamanho": total, "baixado": baixado})
                            return
                        f.write(chunk)
                        baixado += len(chunk)
                        agora = time.time()
                        if agora - t_ui >= 0.25:
                            elapsed = max(agora - t0, 0.001)
                            on_update({
                                "estado":     "baixando",
                                "progresso":  baixado / total if total else 0,
                                "velocidade": (baixado / elapsed) / 1024,
                                "nome":       nome,
                                "tamanho":    total,
                                "baixado":    baixado,
                            })
                            t_ui = agora
            finally:
                try:
                    resp.close()
                except Exception:
                    pass

            self.handles.pop(item_id, None)
            on_update({"estado": "concluido", "progresso": 1.0,
                       "velocidade": 0, "nome": nome,
                       "tamanho": total, "baixado": total})

        except requests.HTTPError as e:
            self.handles.pop(item_id, None)
            on_update({"estado": "erro", "progresso": 0, "velocidade": 0,
                       "nome": f"HTTP {e.response.status_code}", "tamanho": 0})
        except requests.ConnectionError:
            self.handles.pop(item_id, None)
            on_update({"estado": "erro", "progresso": 0, "velocidade": 0,
                       "nome": "Sem conexão com o Mediafire.", "tamanho": 0})
        except requests.Timeout:
            self.handles.pop(item_id, None)
            on_update({"estado": "erro", "progresso": 0, "velocidade": 0,
                       "nome": "Timeout (30s).", "tamanho": 0})
        except Exception as e:
            self.handles.pop(item_id, None)
            on_update({"estado": "erro", "progresso": 0, "velocidade": 0,
                       "nome": str(e), "tamanho": 0})

    def cancelar(self, item_id):
        self._cancelados.add(item_id)

    def parar(self):
        self._cancelados.update(self.handles.keys())


# JANELA DO UNLOCKER
class UnlockerWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("EA Unlocker Manager")
        self.geometry("500x400")
        self.attributes("-topmost", True)
        self.unlocker = EAUnlocker()

        self.status_label = ctk.CTkLabel(self, text="Inicializando...",
                                         font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=20)

        self.prefix_var  = ctk.StringVar(value="Carregando...")
        self.prefix_menu = ctk.CTkOptionMenu(self, variable=self.prefix_var, values=[])
        self.prefix_menu.pack(pady=10)

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(pady=10)
        ctk.CTkButton(bf, text="Instalar / Atualizar",
                      command=self._install).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="Desinstalar", fg_color="#8B0000",
                      command=self._uninstall).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="Abrir Configs",
                      command=self._open_configs).pack(side="left", padx=5)

        self.after(100, self._scan)

    def _scan(self):
        try:
            self.unlocker.discover_prefixes()
            names = self.unlocker.all_prefix_names
            if not names:
                self.prefix_var.set("Nenhum prefixo encontrado")
                self.status_label.configure(text="Nenhum prefixo encontrado.")
                return
            self.prefix_menu.configure(values=names)
            self.prefix_var.set(names[0])
            self.status_label.configure(text=f"{len(names)} prefixo(s) encontrado(s).")
        except Exception as e:
            self.status_label.configure(text=f"Erro: {e}")

    def _select(self):
        names = self.prefix_menu.cget("values")
        if names:
            try:
                self.unlocker.select_prefix(list(names).index(self.prefix_var.get()))
            except Exception as e:
                self.status_label.configure(text=f"Erro: {e}")

    def _install(self):
        self._select()
        threading.Thread(target=self._do, args=("install",), daemon=True).start()

    def _uninstall(self):
        self._select()
        threading.Thread(target=self._do, args=("uninstall",), daemon=True).start()

    def _do(self, acao):
        try:
            if acao == "install":
                self.unlocker.install_unlocker()
                msg = "Instalação concluída!"
            else:
                self.unlocker.uninstall_unlocker()
                msg = "Desinstalação concluída."
            self.after(0, lambda: self.status_label.configure(text=msg))
        except Exception as e:
            self.after(0, lambda: self.status_label.configure(text=f"Falha: {e}"))

    def _open_configs(self):
        try:
            self._select()
            self.unlocker.open_configs_folder()
        except Exception as e:
            self.status_label.configure(text=f"Erro: {e}")


# CARD DE ARQUIVO
class CartaoArquivo(ctk.CTkFrame):
    def __init__(self, master, item_id, item, on_baixar, **kwargs):
        super().__init__(master, corner_radius=12,
                         fg_color=("#EAEAEA", "#242424"), **kwargs)
        self.item_id      = item_id
        self.item         = item
        self.on_baixar    = on_baixar
        self._on_cancelar = None

        self.grid_columnconfigure(1, weight=1)

        cor = CORES_TAG.get(item["tag"], COR_TAG_PADRAO)
        ctk.CTkLabel(self, text=item["tag"],
                     fg_color=cor, text_color="white",
                     corner_radius=8, width=60, height=26,
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, padx=(14, 10), pady=14, sticky="n")

        nome_row = ctk.CTkFrame(self, fg_color="transparent")
        nome_row.grid(row=0, column=1, sticky="w", pady=(14, 0))
        ctk.CTkLabel(nome_row, text=item["nome"], anchor="w",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        self.lbl_tam = ctk.CTkLabel(nome_row, text="", text_color="gray60",
                                    font=ctk.CTkFont(size=11))
        self.lbl_tam.pack(side="left", padx=(8, 0))

        self.lbl_status = ctk.CTkLabel(self, text="Aguardando", anchor="w",
                                       text_color="gray60",
                                       font=ctk.CTkFont(size=11))
        self.lbl_status.grid(row=1, column=1, sticky="w", pady=(2, 6))

        self.bar = ctk.CTkProgressBar(self)
        self.bar.set(0)
        self.bar.grid(row=2, column=1, sticky="ew", pady=(0, 14), padx=(0, 10))

        col_btn = ctk.CTkFrame(self, fg_color="transparent")
        col_btn.grid(row=0, column=2, rowspan=3, padx=(0, 14), pady=14)

        self.btn_baixar = ctk.CTkButton(col_btn, text="⬇ Baixar",
                                        width=100, command=self._clicar)
        self.btn_baixar.pack()

        self.btn_cancel = ctk.CTkButton(col_btn, text="✕ Cancelar",
                                        width=100, fg_color="#5c1a1a",
                                        hover_color="#8B0000",
                                        command=self._cancelar)
        self.btn_cancel.pack(pady=(6, 0))
        self.btn_cancel.pack_forget()

    def _clicar(self):
        self.btn_baixar.configure(state="disabled", text="Baixando...")
        self.lbl_status.configure(text="Iniciando...")
        self.btn_cancel.pack(pady=(6, 0))
        self.on_baixar(self.item_id, self.item)

    def _cancelar(self):
        self.btn_cancel.configure(state="disabled", text="Cancelando…")
        if self._on_cancelar:
            self._on_cancelar(self.item_id)


# JANELA DE PROGRESSO

class JanelaProgresso(ctk.CTkToplevel):
    def __init__(self, master, titulo, subtitulo):
        super().__init__(master)
        self.title(titulo)
        self.geometry("540x280")
        self.resizable(False, False)
        self.grab_set()

        ctk.CTkLabel(self, text=titulo,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(24, 2))
        ctk.CTkLabel(self, text=subtitulo, text_color="gray60",
                     font=ctk.CTkFont(size=11)).pack(pady=(0, 16))

        rg = ctk.CTkFrame(self, fg_color="transparent")
        rg.pack(fill="x", padx=30)
        self.lbl_g = ctk.CTkLabel(rg, text="Aguardando…", text_color="gray60",
                                   font=ctk.CTkFont(size=10), anchor="w")
        self.lbl_g.pack(side="left")
        self.lbl_c = ctk.CTkLabel(rg, text="0 / 0", text_color="gray60",
                                   font=ctk.CTkFont(size=10), anchor="e")
        self.lbl_c.pack(side="right")

        self.bar_g = ctk.CTkProgressBar(self, width=480)
        self.bar_g.set(0)
        self.bar_g.pack(padx=30, pady=(4, 14))

        self.lbl_a = ctk.CTkLabel(self, text="", text_color="gray60",
                                   font=ctk.CTkFont(size=10), anchor="w")
        self.lbl_a.pack(fill="x", padx=30)

        self.bar_a = ctk.CTkProgressBar(self, width=480, progress_color="#2FA572")
        self.bar_a.set(0)
        self.bar_a.pack(padx=30, pady=(4, 0))

        self.lbl_d = ctk.CTkLabel(self, text="", text_color="gray60",
                                   font=ctk.CTkFont(size=9))
        self.lbl_d.pack(pady=(4, 0))

    def atualizar(self, g_txt, c_txt, g_pct, a_txt, a_pct, d_txt=""):
        self.lbl_g.configure(text=g_txt)
        self.lbl_c.configure(text=c_txt)
        self.bar_g.set(g_pct)
        self.lbl_a.configure(text=a_txt)
        self.bar_a.set(a_pct)
        self.lbl_d.configure(text=d_txt)


# APP PRINCIPAL
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DLC Unlocker by LinaPy")
        self.geometry("680x620")
        self.minsize(520, 420)
        self.config_dados = carregar_config()
        ARQUIVOS.extend(carregar_catalogo())
        self.gerenciador  = GerenciadorDownloads(
            pasta_downloads=self.config_dados["pasta_downloads"],
            log=self._log)
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(hdr, text="DLC Unlocker",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="📂 Mover", width=90,
                      fg_color="#1a5c2a", hover_color="#14451f",
                      command=self._abrir_mover).pack(side="right", padx=(4, 0))
        ctk.CTkButton(hdr, text="📦 Extrair", width=90,
                      fg_color="#1a3a5c", hover_color="#14293f",
                      command=self._abrir_extrair).pack(side="right", padx=(4, 0))
        ctk.CTkButton(hdr, text="🛠 EA Unlocker", width=120,
                      command=self._abrir_unlocker).pack(side="right", padx=(4, 0))
        self.lbl_count = ctk.CTkLabel(hdr, text=f"{len(ARQUIVOS)} itens",
                                      text_color="gray60",
                                      font=ctk.CTkFont(size=13))
        self.lbl_count.pack(side="right", padx=(0, 10))

        pf = ctk.CTkFrame(self, fg_color="transparent")
        pf.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(pf, text="Pasta de downloads:",
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self.entry_pasta = ctk.CTkEntry(pf)
        self.entry_pasta.insert(0, self.config_dados["pasta_downloads"])
        self.entry_pasta.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(pf, text="Alterar", width=80,
                      command=self._alterar_pasta).pack(side="left")

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(fill="x", padx=20, pady=(0, 10))
        self.entry_busca = ctk.CTkEntry(
            bf, placeholder_text="🔍 Filtrar por nome ou tag...")
        self.entry_busca.pack(fill="x")
        self.entry_busca.bind("<KeyRelease>", lambda e: self._filtrar())

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self.scroll.grid_columnconfigure(0, weight=1)

        self.cartoes = {}
        self._montar_lista()

        self.lbl_log = ctk.CTkLabel(self, text="", text_color="gray60",
                                    anchor="w", font=ctk.CTkFont(size=11))
        self.lbl_log.pack(fill="x", padx=20, pady=(0, 16))

    def _abrir_unlocker(self):
        for w in self.winfo_children():
            if isinstance(w, UnlockerWindow):
                w.lift(); return
        UnlockerWindow(self).focus_force()

    def _log(self, msg):
        self.after(0, lambda: self.lbl_log.configure(text=msg))
        try:
            escrever_log(msg)
        except Exception:
            pass

    def _montar_lista(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self.cartoes = {}
        for idx, item in enumerate(ARQUIVOS):
            iid    = item.get("mediafire", "") + str(idx)
            cartao = CartaoArquivo(self.scroll, iid, item, self._baixar_item)
            cartao.pack(fill="x", pady=6)
            self.cartoes[iid] = cartao
            item["_iid"] = iid
        self.lbl_count.configure(text=f"{len(ARQUIVOS)} itens")

    def _filtrar(self):
        termo = self.entry_busca.get().strip().lower()
        n = 0
        for item in ARQUIVOS:
            c = self.cartoes.get(item.get("_iid"))
            if not c:
                continue
            if not termo or termo in item["nome"].lower() or termo in item["tag"].lower():
                c.pack(fill="x", pady=6); n += 1
            else:
                c.pack_forget()
        self.lbl_count.configure(text=f"{n} itens")

    def _baixar_item(self, iid, item):
        url = item.get("mediafire", "")
        if not url:
            self._log(f"⚠ Link não disponível: {item['nome']}")
            c = self.cartoes.get(iid)
            if c:
                c.btn_baixar.configure(state="normal", text="⬇ Baixar")
                c.lbl_status.configure(text="Link não disponível")
                c.btn_cancel.pack_forget()
            return

        def on_update(info):
            c = self.cartoes.get(iid)
            if not c:
                return
            estado  = info["estado"]
            prog    = info["progresso"]
            vel     = info["velocidade"]
            nome    = info["nome"]
            total   = info.get("tamanho", 0)
            baixado = info.get("baixado", 0)
            v_txt   = f"{vel/1024:.1f} MB/s" if vel >= 1024 else f"{vel:.0f} KB/s"

            if estado == "resolvendo":
                self.after(0, lambda: c.lbl_status.configure(
                    text="Resolvendo link…", text_color="gray60"))

            elif estado == "iniciando":
                tam_txt = f"({formatar_tamanho(total)})" if total else ""
                self.after(0, lambda t=tam_txt: [
                    c.lbl_tam.configure(text=t),
                    c.lbl_status.configure(text="Conectando…", text_color="gray60"),
                ])

            elif estado == "baixando":
                b_txt = formatar_tamanho(baixado)
                t_txt = formatar_tamanho(total) if total else "?"
                self.after(0, lambda p=prog, v=v_txt, b=b_txt, t=t_txt: [
                    c.bar.set(p),
                    c.lbl_status.configure(
                        text=f"Baixando • {p*100:.1f}% • {b} / {t} • {v}",
                        text_color="gray60"),
                ])

            elif estado == "concluido":
                self.after(0, lambda: [
                    c.bar.set(1.0),
                    c.lbl_status.configure(text="Concluído ✔", text_color="#2FA572"),
                    c.btn_baixar.configure(text="Concluído", state="disabled"),
                    c.btn_cancel.pack_forget(),
                ])
                self._log(f"✔ Concluído: {item['nome']}")

            elif estado == "cancelado":
                self.after(0, lambda: [
                    c.lbl_status.configure(text="Cancelado", text_color="gray60"),
                    c.bar.set(0),
                    c.btn_baixar.configure(state="normal", text="⬇ Baixar"),
                    c.btn_cancel.pack_forget(),
                    c.btn_cancel.configure(state="normal", text="✕ Cancelar"),
                ])
                self._log(f"Cancelado: {item['nome']} (arquivo mantido)")

            elif estado == "erro":
                self.after(0, lambda n=nome: [
                    c.lbl_status.configure(text=f"✘ {n}", text_color="#ef4444"),
                    c.btn_baixar.configure(state="normal", text="⬇ Baixar"),
                    c.btn_cancel.pack_forget(),
                ])
                self._log(f"✘ Erro: {item['nome']}: {nome}")

        self.gerenciador.iniciar(iid, url, on_update)
        self._log(f"Iniciando: {item['nome']}")
        c = self.cartoes.get(iid)
        if c:
            c._on_cancelar = self.gerenciador.cancelar

    def _alterar_pasta(self):
        nova = filedialog.askdirectory(
            title="Escolher pasta", initialdir=self.config_dados["pasta_downloads"])
        if nova:
            self.entry_pasta.delete(0, "end")
            self.entry_pasta.insert(0, nova)
            self.config_dados["pasta_downloads"] = nova
            self.gerenciador.atualizar_pasta(nova)
            salvar_config(self.config_dados)
            self._log(f"Pasta: {nova}")

    def _fechar(self):
        self.gerenciador.parar()
        self.destroy()

    def _pasta_dl(self):
        return Path(self.config_dados["pasta_downloads"])

    def _encontrar_sims(self):
        home = Path.home()
        caminhos = [
            home / ".local/share/Steam",
            home / ".steam/steam",
            home / "snap/steam/common/.local/share/Steam",
            home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
            home / ".var/app/com.valvesoftware.Steam/.steam/steam",
        ]
        for steam in caminhos:
            sims = steam / "steamapps/common/The Sims 4"
            if sims.exists():
                return sims
            vdf = steam / "steamapps/libraryfolders.vdf"
            if vdf.exists():
                try:
                    txt = vdf.read_text(encoding="utf-8", errors="ignore")
                    for p in re.findall(r'"path"\s+"([^"]+)"', txt):
                        sims = Path(p) / "steamapps/common/The Sims 4"
                        if sims.exists():
                            return sims
                except Exception:
                    pass
        return None

    # Extrair 
    def _abrir_extrair(self):
        pasta = self._pasta_dl()
        zips  = list(pasta.glob("*.zip"))
        if not zips:
            messagebox.showwarning("Nada encontrado",
                                   f"Nenhum .zip em:\n{pasta}")
            return
        win = JanelaProgresso(self, "📦 Extraindo DLCs",
                              f"{len(zips)} arquivo(s) encontrado(s)")
        threading.Thread(target=self._run_extrair,
                         args=(zips, win), daemon=True).start()

    def _run_extrair(self, zips, win):
        total = len(zips)
        erros = []
        for i, zp in enumerate(zips):
            nome  = zp.stem
            dest  = zp.parent / nome
            self.after(0, lambda n=nome, i=i, t=total: win.atualizar(
                f"Extraindo: {n}", f"{i} / {t}", i / t, "Preparando…", 0))
            try:
                dest.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zp, "r") as zf:
                    membros = zf.infolist()
                    tm = len(membros)
                    for j, m in enumerate(membros):
                        zf.extract(m, dest)
                        p = (j + 1) / tm
                        self.after(0,
                            lambda p=p, j=j, tm=tm, n=nome, i=i, t=total:
                            win.atualizar(f"Extraindo: {n}", f"{i+1} / {t}",
                                          (i + p) / t, f"Arquivo {j+1} de {tm}",
                                          p, f"{j+1} / {tm}"))
                self._log(f"✔ Extraído: {nome}")
            except zipfile.BadZipFile:
                erros.append(f"{nome}: zip corrompido")
            except Exception as e:
                erros.append(f"{nome}: {e}")

        def fim():
            win.destroy()
            msg = f"Extração concluída!\n{total - len(erros)} de {total}."
            if erros:
                msg += "\n\nErros:\n" + "\n".join(f"• {e}" for e in erros)
                messagebox.showwarning("Erros na extração", msg)
            else:
                messagebox.showinfo("Extração concluída", msg)
        self.after(0, fim)

    # Mover 
    def _abrir_mover(self):
        pasta = self._pasta_dl()
        try:
            pastas = [p for p in pasta.iterdir()
                      if p.is_dir() and re.match(r'Sims4_DLC_', p.name, re.IGNORECASE)]
        except FileNotFoundError:
            pastas = []
        if not pastas:
            messagebox.showwarning("Nada encontrado",
                                   f"Nenhuma pasta extraída em:\n{pasta}\n\n"
                                   "Execute primeiro 📦 Extrair.")
            return
        sims = self._encontrar_sims()
        if not sims:
            messagebox.showerror("Sims 4 não encontrado",
                                 "Não foi possível localizar The Sims 4.\n"
                                 "Certifique-se de que está instalado via Steam.")
            return
        win = JanelaProgresso(self, "📂 Movendo DLCs",
                              f"{len(pastas)} pasta(s) encontrada(s)")
        threading.Thread(target=self._run_mover,
                         args=(pastas, sims, win), daemon=True).start()

    def _run_mover(self, pastas, sims, win):
        total   = len(pastas)
        erros   = []
        pulados = []
        pad     = re.compile(r'^(EP|GP|SP|FP|KT)\d+', re.IGNORECASE)
        dst_r   = sims
        dst_d   = sims / "__Installer" / "DLC"

        for i, pasta in enumerate(pastas):
            nome = pasta.name
            self.after(0, lambda n=nome, i=i, t=total: win.atualizar(
                f"Processando: {n}", f"{i} / {t}", i / t, "Localizando…", 0))

            raiz = next((p for p in pasta.iterdir()
                         if p.is_dir() and pad.match(p.name)), None)
            dlc_dir = None
            inst = pasta / "__Installer" / "DLC"
            if inst.exists():
                dlc_dir = next((p for p in inst.iterdir()
                                if p.is_dir() and pad.match(p.name)), None)

            for src, base, label in [(raiz, dst_r, "raiz"),
                                     (dlc_dir, dst_d, "__Installer/DLC")]:
                if src is None:
                    continue
                dst = base / src.name
                if dst.exists():
                    ev, res = threading.Event(), [False]
                    def ask(s=src, lb=label, ev=ev, res=res):
                        res[0] = messagebox.askyesno(
                            "Já existe",
                            f"'{s.name}' já existe em {lb}.\n\nSubstituir?")
                        ev.set()
                    self.after(0, ask)
                    ev.wait()
                    if not res[0]:
                        pulados.append(f"{src.name} em {label}"); continue
                    shutil.rmtree(dst)
                base.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                self._log(f"✔ Movido: {src.name} → {label}")

            self.after(0, lambda n=nome, i=i+1, t=total: win.atualizar(
                f"Concluído: {n}", f"{i} / {t}", i / t, "Concluído", 1.0))

        def fim():
            win.destroy()
            msg = "Movimento concluído!"
            if pulados:
                msg += f"\n\nPulados:\n" + "\n".join(f"• {p}" for p in pulados)
            if erros:
                msg += f"\n\nErros:\n" + "\n".join(f"• {e}" for e in erros)
            (messagebox.showwarning if erros else messagebox.showinfo)(
                "Concluído com erros" if erros else "Concluído", msg)
        self.after(0, fim)


if __name__ == "__main__":
    def abrir_app():
        App().mainloop()

    SplashScreen(
        caminho_imagem=str(BASE_DIR / "assets" / "__.jpeg"),
        texto=(
            "A pirataria surge quando o valor de uma obra\n"
            "encontra a realidade de quem não pode alcançá-la.\n\n"
            "pirateie TUDO que você puder!"
        ),
        ao_continuar=abrir_app,
    ).mainloop()
