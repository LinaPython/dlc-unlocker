#!/bin/bash
set -e

VERDE="\033[0;32m"
AMARELO="\033[1;33m"
VERMELHO="\033[0;31m"
CIANO="\033[0;36m"
RESET="\033[0m"

info()  { echo -e "${CIANO}[INFO]${RESET}  $1"; }
ok()    { echo -e "${VERDE}[OK]${RESET}    $1"; }
aviso() { echo -e "${AMARELO}[AVISO]${RESET} $1"; }
erro()  { echo -e "${VERMELHO}[ERRO]${RESET}  $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo -e "${CIANO}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CIANO}║         DLC Unlocker — Uninstall         ║${RESET}"
echo -e "${CIANO}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── confirmação ──────────────────────────────────────────────
read -r -p "$(echo -e "${AMARELO}Deseja remover o DLC Unlocker? [s/N]:${RESET} ")" resposta
case "$resposta" in
    [sS]) ;;
    *) info "Cancelado."; exit 0 ;;
esac

echo ""

if [ -d "$SCRIPT_DIR/.venv" ]; then
    info "Removendo .venv..."
    rm -rf "$SCRIPT_DIR/.venv"
    ok ".venv removida."
else
    aviso ".venv não encontrada — pulando."
fi

if [ -f "$SCRIPT_DIR/run.sh" ]; then
    info "Removendo run.sh..."
    rm -f "$SCRIPT_DIR/run.sh"
    ok "run.sh removido."
fi

if [ -d "$SCRIPT_DIR/configs" ]; then
    read -r -p "$(echo -e "${AMARELO}Remover configs e cache de imagens? [s/N]:${RESET} ")" resp_cfg
    case "$resp_cfg" in
        [sS])
            rm -rf "$SCRIPT_DIR/configs"
            ok "configs/ removida."
            ;;
        *)
            aviso "configs/ mantida."
            ;;
    esac
fi

if [ -d "$SCRIPT_DIR/logs" ]; then
    read -r -p "$(echo -e "${AMARELO}Remover logs? [s/N]:${RESET} ")" resp_log
    case "$resp_log" in
        [sS])
            rm -rf "$SCRIPT_DIR/logs"
            ok "logs/ removida."
            ;;
        *)
            aviso "logs/ mantida."
            ;;
    esac
fi
DESKTOP="$HOME/.local/share/applications/dlc-unlocker.desktop"
if [ -f "$DESKTOP" ]; then
    info "Removendo atalho .desktop..."
    rm -f "$DESKTOP"
    update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
    ok "Atalho removido."
else
    aviso "Atalho .desktop não encontrado — pulando."
fi

info "Limpando __pycache__..."
find "$SCRIPT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
ok "__pycache__ limpo."

echo ""
ok "Desinstalação concluída."
echo ""
echo -e "  Os arquivos do projeto em ${CIANO}$SCRIPT_DIR${RESET} foram mantidos."
echo -e "  Para remover completamente: ${CIANO}rm -rf $SCRIPT_DIR${RESET}"
echo ""