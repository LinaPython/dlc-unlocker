# gui/app.py 
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject, QMetaObject, Q_ARG
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea,
    QFileDialog, QMessageBox, QFrame, QApplication,
    QComboBox, QTabWidget
)

from core.catalog     import carregar_catalogo
from core.config      import carregar_config, salvar_config
from core.downloader  import GerenciadorDownloads
from core.extractor   import extrair_zips
from core.mover       import mover_dlcs
from core.sims_finder import encontrar_sims
from core.logger      import escrever_log
from core.updater     import checar_atualizacao, versao_local

from gui.card_widget     import CardArquivo
from gui.progress_dialog import ProgressDialog
from gui.unlocker_dialog import UnlockerDialog
from gui.update_dialog   import UpdateDialog
from gui import theme as _theme
from gui.bg_window import BgWindow

class _Sinais(QObject):
    log             = Signal(object)   
    catalogo_pronto = Signal(list)
    pedir_confirmacao = Signal(str, str)


class MainWindow(BgWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DLC Unlocker by LinaPython")
        self.setMinimumSize(680, 620)
        self.resize(760, 680)

        self._config    = carregar_config()
        self._arquivos: list[dict] = []
        self._cards:    dict[str, CardArquivo] = {}
        self._sinais    = _Sinais()
        self._sinais.log.connect(self._set_log)
        self._sinais.catalogo_pronto.connect(self._montar_lista)

        self._confirmacao_ev  = threading.Event()
        self._confirmacao_res = [False]
        self._sinais.pedir_confirmacao.connect(self._mostrar_confirmacao)
        self._gerenciador = GerenciadorDownloads(
            pasta_downloads=self._config["pasta_downloads"],
            log=lambda m: self._sinais.log.emit(m),
        )

        self._dlg_extrair = None
        self._dlg_mover   = None

        self._build_ui()
        _BG: dict[str, str] = {"rosa-glass": "assets/p.jpg", "black": "assets/black.jpg", "white": "assets/white.jpg",}
        bg = _BG.get(self._config.get("tema", "dark"))
        if bg:
            self.set_background(bg)
        threading.Thread(target=self._carregar_catalogo, daemon=True).start()
        self._checar_update()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(10)

        hdr = QHBoxLayout()

        lbl_title = QLabel("DLC Unlocker")
        lbl_title.setObjectName("lbl_title")
        hdr.addWidget(lbl_title)
        hdr.addStretch()

        self.lbl_count = QLabel("carregando...")
        self.lbl_count.setObjectName("lbl_muted")
        hdr.addWidget(self.lbl_count)

        self.combo_tema = QComboBox()
        self.combo_tema.setFixedWidth(130)
        self.combo_tema.addItems(_theme.available())
        self.combo_tema.setCurrentText(_theme.current())
        self.combo_tema.currentTextChanged.connect(self._trocar_tema)
        hdr.addWidget(self.combo_tema)

        btn_unlocker = QPushButton("EA Unlocker")
        btn_unlocker.clicked.connect(self._abrir_unlocker)
        hdr.addWidget(btn_unlocker)

        btn_aplicar = QPushButton("Aplicar DLCs")
        btn_aplicar.setObjectName("btn_success")
        btn_aplicar.clicked.connect(self._abrir_aplicar)
        hdr.addWidget(btn_aplicar)

        root.addLayout(hdr)

        pf = QHBoxLayout()
        pf.addWidget(QLabel("Pasta de downloads:"))
        self.entry_pasta = QLineEdit(self._config["pasta_downloads"])
        pf.addWidget(self.entry_pasta, 1)
        btn_pasta = QPushButton("Alterar")
        btn_pasta.setFixedWidth(80)
        btn_pasta.clicked.connect(self._alterar_pasta)
        pf.addWidget(btn_pasta)
        root.addLayout(pf)

        self.entry_busca = QLineEdit()
        self.entry_busca.setPlaceholderText("Filtrar por nome ou tag...")
        self.entry_busca.textChanged.connect(self._filtrar)
        root.addWidget(self.entry_busca)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("main_tabs")

        self._tab_s4 = QWidget()
        self._build_tab_s4(self._tab_s4)
        self.tabs.addTab(self._tab_s4, "The Sims 4")

        self._tab_s3 = QWidget()
        self._build_tab_s3(self._tab_s3)
        self.tabs.addTab(self._tab_s3, "The Sims 3")

        root.addWidget(self.tabs, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        rodape = QHBoxLayout()
        self.lbl_log = QLabel("")
        self.lbl_log.setObjectName("lbl_muted")
        rodape.addWidget(self.lbl_log, 1)

        self.lbl_versao = QLabel(f"v{versao_local()}")
        self.lbl_versao.setObjectName("lbl_muted")
        self.lbl_versao.setAlignment(Qt.AlignmentFlag.AlignRight)
        rodape.addWidget(self.lbl_versao)
        root.addLayout(rodape)

    def _abrir_aplicar(self) -> None:
        pasta = self._pasta_dl()
        zips  = list(pasta.glob("*.zip"))

        if not zips:
            QMessageBox.warning(
                self, "Nada encontrado",
                f"Nenhum .zip em:\n{pasta}"
            )
            return

        sims = encontrar_sims()
        if not sims:
            QMessageBox.critical(
                self, "Sims 4 nao encontrado",
                "Nao foi possivel localizar The Sims 4.\n"
                "Certifique-se de que esta instalado via Steam."
            )
            return

        dlg = ProgressDialog(
            "Aplicando DLCs",
            f"{len(zips)} arquivo(s) encontrado(s)",
            self,
        )
        dlg.show()
        self._dlg_extrair = dlg
        self._dlg_mover   = dlg  

        def run() -> None:
            def on_progress_zip(nome, i, total, membro, j, tm):
                self._sinais.log.emit(
                    f"__prog_extrair__{nome}||{i}||{total}||{j}||{tm}"
                )

            def on_erro_zip(msg):
                self._sinais.log.emit(f"Erro ao extrair: {msg}")

            n_ok, erros_zip = extrair_zips(pasta, on_progress_zip, on_erro_zip)

            if erros_zip:
                self._sinais.log.emit(
                    f"Extracao com {len(erros_zip)} erro(s) — continuando para mover..."
                )

            try:
                pastas = [
                    p for p in pasta.iterdir()
                    if p.is_dir() and p.name.lower().startswith("sims4_dlc_")
                ]
            except FileNotFoundError:
                pastas = []

            def on_progress_mv(nome: str, i: int, total: int) -> None:
                self._sinais.log.emit(f"__prog_mover__{nome}||{i}||{total}")

            def on_confirmar(nome: str, label: str) -> bool:
                self._confirmacao_ev.clear()
                self._sinais.pedir_confirmacao.emit(nome, label)
                self._confirmacao_ev.wait()
                return self._confirmacao_res[0]

            pulados, erros_mv = mover_dlcs(
                pasta, sims, on_progress_mv, on_confirmar,
                on_log=lambda m: self._sinais.log.emit(m),
            )

            def fim() -> None:
                self._dlg_extrair = None
                self._dlg_mover   = None
                dlg.close()

                msg = f"Extracao: {n_ok} de {len(zips)} OK.\n"
                msg += f"Movidos: {len(pastas) - len(erros_mv)} de {len(pastas)}."

                if pulados:
                    msg += "\n\nPulados:\n" + "\n".join(f"  {p}" for p in pulados)
                if erros_zip or erros_mv:
                    erros = erros_zip + erros_mv
                    msg += "\n\nErros:\n" + "\n".join(f"  {e}" for e in erros)
                    QMessageBox.warning(self, "Concluido com erros", msg)
                else:
                    QMessageBox.information(self, "Concluido", msg)

            self._sinais.log.emit(fim)

        threading.Thread(target=run, daemon=True).start()

    def _build_tab_s4(self, parent: QWidget) -> None:
        from gui.smooth_scroll import SmoothScrollArea

        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        self._scroll_widget = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(8)
        self._scroll_layout.addStretch()

        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._scroll_widget)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll)
    def _build_tab_s3(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel("Em breve")
        lbl.setObjectName("lbl_title")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        lbl_sub = QLabel(
            "Estou trabalhando no catalogo do The Sims 3.\n"
            "Em breve os DLCs estarao disponiveis aqui."
        )
        lbl_sub.setObjectName("lbl_muted")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_sub)

    def _carregar_catalogo(self) -> None:
        dados = carregar_catalogo()
        self._sinais.catalogo_pronto.emit(dados)

    def _montar_lista(self, arquivos: list[dict]) -> None:
        for card in self._cards.values():
            card.deleteLater()
        self._cards.clear()

        item = self._scroll_layout.takeAt(self._scroll_layout.count() - 1)
        del item

        self._arquivos = arquivos
        for idx, item in enumerate(self._arquivos):
            iid = item.get("mediafire", "") + str(idx)
            item["_iid"] = iid
            card = CardArquivo(
                item_id=iid,
                item=item,
                on_baixar=self._baixar_item,
                on_cancelar=self._gerenciador.cancelar,
            )
            self._scroll_layout.addWidget(card)
            self._cards[iid] = card

        self._scroll_layout.addStretch()
        self.lbl_count.setText(f"{len(self._arquivos)} itens")

    def _filtrar(self, termo: str = "") -> None:
        termo = termo.strip().lower()
        n = 0
        for item in self._arquivos:
            card = self._cards.get(item.get("_iid", ""))
            if not card:
                continue
            visivel = (
                not termo
                or termo in item.get("nome", "").lower()
                or termo in item.get("tag",  "").lower()
            )
            card.setVisible(visivel)
            if visivel:
                n += 1
        self.lbl_count.setText(f"{n} itens")

    def _baixar_item(self, iid: str, item: dict) -> None:
        url = item.get("mediafire", "")
        if not url:
            self._log(f"Link nao disponivel: {item['nome']}")
            card = self._cards.get(iid)
            if card:
                card.btn_baixar.setEnabled(True)
                card.btn_baixar.setText("Baixar")
                card.btn_cancel.hide()
            return

        def on_update(info: dict) -> None:
            card = self._cards.get(iid)
            if card:
                card.emitir_update(info)
            if info["estado"] == "concluido":
                self._log(f"Concluido: {item['nome']}")
            elif info["estado"] == "erro":
                self._log(f"Erro: {item['nome']}: {info['nome']}")
            elif info["estado"] == "cancelado":
                self._log(f"Cancelado: {item['nome']}")

        self._gerenciador.iniciar(iid, url, on_update)
        self._log(f"Iniciando: {item['nome']}")

    def _alterar_pasta(self) -> None:
        nova = QFileDialog.getExistingDirectory(
            self, "Escolher pasta", self._config["pasta_downloads"]
        )
        if nova:
            self.entry_pasta.setText(nova)
            self._config["pasta_downloads"] = nova
            self._gerenciador.atualizar_pasta(nova)
            salvar_config(self._config)
            self._log(f"Pasta: {nova}")

    def _pasta_dl(self) -> Path:
        return Path(self._config["pasta_downloads"])

    def _abrir_extrair(self) -> None:
        pasta = self._pasta_dl()
        zips  = list(pasta.glob("*.zip"))
        if not zips:
            QMessageBox.warning(self, "Nada encontrado", f"Nenhum .zip em:\n{pasta}")
            return

        dlg = ProgressDialog("Extraindo DLCs", f"{len(zips)} arquivo(s) encontrado(s)", self)
        dlg.show()
        self._dlg_extrair = dlg

        def run() -> None:
            def on_progress(nome, i, total, membro, j, tm):
                self._sinais.log.emit(f"__prog_extrair__{nome}||{i}||{total}||{j}||{tm}")

            def on_erro(msg):
                self._sinais.log.emit(f"Erro: {msg}")

            n_ok, erros = extrair_zips(pasta, on_progress, on_erro)

            def fim() -> None:
                self._dlg_extrair = None
                dlg.close()
                msg = f"Extracao concluida!\n{n_ok} de {len(zips)}."
                if erros:
                    msg += "\n\nErros:\n" + "\n".join(f"  {e}" for e in erros)
                    QMessageBox.warning(self, "Erros na extracao", msg)
                else:
                    QMessageBox.information(self, "Extracao concluida", msg)

            self._sinais.log.emit(fim)

        threading.Thread(target=run, daemon=True).start()

    def _abrir_mover(self) -> None:
        pasta = self._pasta_dl()
        try:
            pastas = [
                p for p in pasta.iterdir()
                if p.is_dir() and p.name.lower().startswith("sims4_dlc_")
            ]
        except FileNotFoundError:
            pastas = []

        if not pastas:
            QMessageBox.warning(
                self, "Nada encontrado",
                f"Nenhuma pasta extraida em:\n{pasta}\n\nExecute primeiro Extrair."
            )
            return

        sims = encontrar_sims()
        print(f"[DEBUG] Sims 4 encontrado em: {sims}")
        if not sims:
            QMesclearsageBox.critical(
                self, "Sims 4 nao encontrado",
                "Nao foi possivel localizar The Sims 4.\n"
                "Certifique-se de que esta instalado via Steam."
            )
            return

        dlg = ProgressDialog("Movendo DLCs", f"{len(pastas)} pasta(s) encontrada(s)", self)
        dlg.show()
        self._dlg_mover = dlg

        def on_progress(nome: str, i: int, total: int) -> None:
            self._sinais.log.emit(f"__prog_mover__{nome}||{i}||{total}")

        def on_confirmar(nome: str, label: str) -> bool:
            self._confirmacao_ev.clear()
            self._sinais.pedir_confirmacao.emit(nome, label)
            self._confirmacao_ev.wait()
            return self._confirmacao_res[0]

        def run() -> None:
            pulados, erros = mover_dlcs(
                pasta, sims, on_progress, on_confirmar,
                on_log=lambda m: self._sinais.log.emit(m),
            )

            def fim() -> None:
                self._dlg_mover = None
                dlg.close()
                msg = "Movimento concluido!"
                if pulados:
                    msg += "\n\nPulados:\n" + "\n".join(f"  {p}" for p in pulados)
                if erros:
                    msg += "\n\nErros:\n" + "\n".join(f"  {e}" for e in erros)
                (QMessageBox.warning if erros else QMessageBox.information)(
                    self,
                    "Concluido com erros" if erros else "Concluido",
                    msg,
                )

            self._sinais.log.emit(fim)

        threading.Thread(target=run, daemon=True).start()

    def _invoke_ask(self, fn, ev) -> None:
        fn()

    def _invoke_fim(self, fn) -> None:
        fn()

    def _abrir_unlocker(self) -> None:
        dlg = UnlockerDialog(self)
        dlg.exec()

    def _trocar_tema(self, nome: str) -> None:
        app = QApplication.instance()
        _theme.apply(app, nome)
        self._config["tema"] = nome
        salvar_config(self._config)
        _BG: dict[str, str] = {
        "rosa-glass": "assets/p.jpg",
        "black": "assets/black.jpg",
        "white": "assets/white.jpg",
        }
        bg = _BG.get(nome)
        if bg:
            self.set_background(bg)
        else:
            self.clear_background()

    def _checar_update(self) -> None:
        ignorar = self._config.get("ignorar_versao", "")

        def on_atualizado(nova: str, local: str, url: str) -> None:
            if ignorar and ignorar == url:
                return
            self._sinais.log.emit(f"__update__{nova}||{local}||{url}")

        def on_sem_atualizacao(local: str) -> None:
            self._sinais.log.emit(f"__versao_ok__{local}")

        checar_atualizacao(on_atualizado, on_sem_atualizacao)

    def _log(self, msg: str) -> None:
        self._sinais.log.emit(msg)

    def _set_log(self, msg) -> None:
        if callable(msg):
            msg()
            return

        if msg.startswith("__prog_extrair__"):
            partes = msg.replace("__prog_extrair__", "").split("||")
            if len(partes) == 5 and self._dlg_extrair:
                nome, i, total, j, tm = partes
                i, total, j, tm = int(i), int(total), int(j), int(tm)
                self._dlg_extrair.atualizar(
                    f"Extraindo: {nome}", f"{i + 1} / {total}",
                    (i + j / tm) / total if tm else 0,
                    f"Arquivo {j} de {tm}", j / tm if tm else 0,
                )
            return

        if msg.startswith("__prog_mover__"):
            partes = msg.replace("__prog_mover__", "").split("||")
            if len(partes) == 3 and self._dlg_mover:
                nome, i, total = partes[0], int(partes[1]), int(partes[2])
                self._dlg_mover.atualizar(
                    f"Processando: {nome}", f"{i} / {total}",
                    i / total if total else 0,
                    "Movendo...", 0,
                )
            return

        if msg.startswith("__update__"):
            partes = msg.replace("__update__", "").split("||")
            if len(partes) == 3:
                dlg = UpdateDialog(partes[0], partes[1], partes[2], self)
                dlg.exec()
            return

        if msg.startswith("__versao_ok__"):
            versao = msg.replace("__versao_ok__", "")
            self.lbl_versao.setText(f"v{versao}  —  atualizado")
            return

        if msg:
            self.lbl_log.setText(msg)
            try:
                escrever_log(msg)
            except Exception:
                pass

    def closeEvent(self, event) -> None:
        self._gerenciador.parar()
        event.accept()

    def _mostrar_confirmacao(self, nome: str, label: str) -> None:
        self._confirmacao_res[0] = QMessageBox.question(
        self, "Ja existe",
        f"'{nome}' ja existe em {label}.\n\nSubstituir?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    ) == QMessageBox.StandardButton.Yes
        self._confirmacao_ev.set()