# core/downloader.py 
import os
import re
import time
import threading
import requests

from html import unescape
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from curl_cffi import requests as cffi_requests
    _CFFI_OK = True
except ImportError:
    _CFFI_OK = False

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)
_CDN_RE = re.compile(r'https://download\d+\.mediafire\.com/[^\s"\'<>]+')


def _nova_sessao(pool: int = 8) -> requests.Session:
    s = requests.Session()
    r = Retry(
        total=3, backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    a = HTTPAdapter(pool_connections=pool, pool_maxsize=pool, max_retries=r)
    s.mount("https://", a)
    s.mount("http://", a)
    return s


def _get_pagina(url: str) -> tuple[str, object]:
    if _CFFI_OK:
        sessao = cffi_requests.Session(impersonate="chrome120")
        for espera in [0, 3, 6]:
            if espera:
                time.sleep(espera)
            resp = sessao.get(url, timeout=20, allow_redirects=True)
            if resp.status_code != 403:
                return resp.text, sessao
        raise ValueError(f"Cloudflare bloqueou após 3 tentativas (403): {url}")
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


def _extrair_link_cdn(html: str) -> str | None:
    m = _CDN_RE.search(unescape(html))
    return m.group(0).rstrip("\"'\\&") if m else None


def formatar_tamanho(bytes_: int) -> str:
    if bytes_ <= 0:
        return "? MB"
    valor = float(bytes_)
    for unidade in ("B", "KB", "MB", "GB"):
        if valor < 1024:
            return f"{valor:.1f} {unidade}"
        valor /= 1024
    return f"{valor:.1f} TB"


def resolver_mediafire(url_pagina: str) -> tuple[str, str, int, object]:
    """Retorna (url_direta, nome_arquivo, tamanho_bytes, sessao)."""
    html, sessao = _get_pagina(url_pagina)
    link = _extrair_link_cdn(html)
    if not link:
        raise ValueError(
            f"Link CDN não encontrado: {url_pagina}\n"
            "Instale curl_cffi para contornar o Cloudflare: pip install curl-cffi"
        )
    nome = requests.utils.unquote(link.split("/")[-1].split("?")[0])
    tamanho = 0
    m = re.search(r'\(([\d.,]+)\s*(KB|MB|GB)\)', html, re.IGNORECASE)
    if m:
        val = float(m.group(1).replace(",", "."))
        mult = {"KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}[m.group(2).upper()]
        tamanho = int(val * mult)
    return link, nome, tamanho, sessao


class GerenciadorDownloads:
    CHUNK = 4 * 1024 * 1024  # 4 MB

    def __init__(self, pasta_downloads: str, log=print):
        self.pasta_downloads = pasta_downloads
        self.log = log
        self._handles: dict[str, bool] = {}
        self._cancelados: set[str] = set()
        self._sessao_dl = _nova_sessao(pool=10)
        self._sessao_dl.headers.update({"User-Agent": _UA})

    def atualizar_pasta(self, nova: str) -> None:
        self.pasta_downloads = nova

    def iniciar(self, item_id: str, url: str, on_update) -> None:
        self._handles[item_id] = True
        threading.Thread(
            target=self._baixar, args=(item_id, url, on_update), daemon=True
        ).start()

    def cancelar(self, item_id: str) -> None:
        self._cancelados.add(item_id)

    def parar(self) -> None:
        self._cancelados.update(self._handles.keys())

    def _baixar(self, item_id: str, url: str, on_update) -> None:
        os.makedirs(self.pasta_downloads, exist_ok=True)
        try:
            on_update({"estado": "resolvendo", "progresso": 0,
                       "velocidade": 0, "nome": "", "tamanho": 0})
            url_dl, nome, tam_pag, sessao_dl = resolver_mediafire(url)
            destino = os.path.join(self.pasta_downloads, nome)
            _headers_dl = {
                "Referer": url,
                "Origin": "https://www.mediafire.com",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
            }
            resp = sessao_dl.get(
                url_dl, stream=True, timeout=30, headers=_headers_dl
            )
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0)) or tam_pag
            baixado = 0
            t0 = time.time()
            t_ui = t0
            on_update({"estado": "iniciando", "progresso": 0,
                       "velocidade": 0, "nome": nome, "tamanho": total})
            try:
                with open(destino, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=self.CHUNK):
                        if not chunk:
                            continue
                        if item_id in self._cancelados:
                            self._cancelados.discard(item_id)
                            self._handles.pop(item_id, None)
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
                                "estado": "baixando",
                                "progresso": baixado / total if total else 0,
                                "velocidade": (baixado / elapsed) / 1024,
                                "nome": nome,
                                "tamanho": total,
                                "baixado": baixado,
                            })
                            t_ui = agora
            finally:
                try:
                    resp.close()
                except Exception:
                    pass

            self._handles.pop(item_id, None)
            on_update({"estado": "concluido", "progresso": 1.0,
                       "velocidade": 0, "nome": nome,
                       "tamanho": total, "baixado": total})

        except requests.HTTPError as e:
            self._handles.pop(item_id, None)
            on_update({"estado": "erro", "progresso": 0, "velocidade": 0,
                       "nome": f"HTTP {e.response.status_code}", "tamanho": 0})
        except requests.ConnectionError:
            self._handles.pop(item_id, None)
            on_update({"estado": "erro", "progresso": 0, "velocidade": 0,
                       "nome": "Sem conexão com o Mediafire.", "tamanho": 0})
        except requests.Timeout:
            self._handles.pop(item_id, None)
            on_update({"estado": "erro", "progresso": 0, "velocidade": 0,
                       "nome": "Timeout (30s).", "tamanho": 0})
        except Exception as e:
            self._handles.pop(item_id, None)
            on_update({"estado": "erro", "progresso": 0, "velocidade": 0,
                       "nome": str(e), "tamanho": 0})