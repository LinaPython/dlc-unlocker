#!/bin/bash
# ============================================================
#  Suporta: Arch, Debian/Ubuntu, Fedora/RHEL, openSUSE, Bazzite
#  Responsabilidade: python3 + pip + git + .venv + requirements.txt
# ============================================================

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
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

echo ""
echo -e "${CIANO}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CIANO}║         DLC Unlocker — Setup             ║${RESET}"
echo -e "${CIANO}╚══════════════════════════════════════════╝${RESET}"
echo ""

[ -f /etc/os-release ] || erro "Não foi possível detectar a distribuição Linux."
. /etc/os-release
DISTRO_ID="${ID}"
DISTRO_LIKE="${ID_LIKE:-}"
info "Distribuição: ${PRETTY_NAME:-$DISTRO_ID}"

IMUTAVEL=false
command -v rpm-ostree &>/dev/null && IMUTAVEL=true

instalar_base() {
    if echo "${DISTRO_ID} ${DISTRO_LIKE}" | grep -qi "arch"; then
        info "pacman: instalando python, pip, git..."
        sudo pacman -Sy --noconfirm --needed python python-pip git

    elif $IMUTAVEL; then
        info "Sistema imutável — verificando python3 e git..."
        command -v python3 &>/dev/null || erro "python3 não encontrado. Instale via: rpm-ostree install python3"
        command -v git     &>/dev/null || aviso "git não encontrado. rpm-ostree install git"
        python3 -m pip --version &>/dev/null || erro "pip não encontrado. Instale via: rpm-ostree install python3-pip"

    elif echo "${DISTRO_ID} ${DISTRO_LIKE}" | grep -qi "debian\|ubuntu"; then
        info "apt: instalando python3, pip, venv, git..."
        sudo apt-get install -y python3 python3-pip python3-venv git \
            || { sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip python3-venv git; }

    elif echo "${DISTRO_ID} ${DISTRO_LIKE}" | grep -qi "fedora\|rhel\|centos"; then
        info "dnf: instalando python3, pip, git..."
        sudo dnf install -y python3 python3-pip git

    elif echo "${DISTRO_ID} ${DISTRO_LIKE}" | grep -qi "suse\|opensuse"; then
        info "zypper: instalando python3, pip, git..."
        sudo zypper install -y python3 python3-pip git

    else
        aviso "Distro '${DISTRO_ID}' não reconhecida."
        command -v python3 &>/dev/null || erro "python3 não encontrado. Instale manualmente."
        command -v pip3    &>/dev/null || erro "pip não encontrado. Instale manualmente."
    fi
}

criar_venv() {
    if [ -d "$VENV_DIR" ]; then
        info ".venv já existe — reutilizando."
    else
        info "Criando .venv em $VENV_DIR..."
        python3 -m venv "$VENV_DIR" || erro "Falha ao criar .venv. Em Debian/Ubuntu instale python3-venv."
        ok ".venv criada."
    fi
}

instalar_requirements() {
    local req="$SCRIPT_DIR/requirements.txt"
    [ -f "$req" ] || erro "requirements.txt não encontrado em $SCRIPT_DIR"

    info "Instalando dependências na .venv..."
    "$VENV_PIP" install --upgrade pip --quiet
    "$VENV_PIP" install -r "$req" \
        || erro "Falha ao instalar requirements.txt."

    ok "Dependências instaladas na .venv."
}

criar_runner() {
    cat > "$SCRIPT_DIR/run.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
exec .venv/bin/python main.py "$@"
EOF
    chmod +x "$SCRIPT_DIR/run.sh"
    ok "run.sh criado."
}

instalar_desktop() {
    local desktop_src="$SCRIPT_DIR/dlc-unlocker.desktop"
    local desktop_dst="$HOME/.local/share/applications/dlc-unlocker.desktop"

    [ -f "$desktop_src" ] || erro "dlc-unlocker.desktop não encontrado em $SCRIPT_DIR"

    info "Criando atalho .desktop..."
    mkdir -p "$HOME/.local/share/applications"

    sed \
        -e "s|Exec=.*|Exec=$SCRIPT_DIR/run.sh|" \
        -e "s|Icon=.*|Icon=$SCRIPT_DIR/assets/icons/dlcunlocker-128.ico|" \
        "$desktop_src" > "$desktop_dst"

    chmod +x "$desktop_dst"
    update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
    ok "Atalho criado em $desktop_dst"
}

verificar() {
    echo ""
    info "Verificando dependências na .venv..."

    local falhas=0
    check() {
        if "$VENV_PY" -c "$2" 2>/dev/null; then
            ok "$1"
        else
            aviso "$1 — NÃO encontrado"
            falhas=$((falhas + 1))
        fi
    }

    check "Python 3.10+"   "import sys; assert sys.version_info >= (3,10)"
    check "PySide6"        "import PySide6"
    check "requests"       "import requests"
    check "BeautifulSoup4" "import bs4"
    check "Pillow"         "from PIL import Image"
    check "curl_cffi"      "import curl_cffi"

    echo ""
    if [ "$falhas" -eq 0 ]; then
        ok "Tudo pronto."
        echo ""
        echo -e "  Para iniciar:"
        echo -e "  ${CIANO}./run.sh${RESET}"
        echo ""
    else
        aviso "$falhas dependência(s) não encontrada(s)."
        echo ""
        echo -e "  Tente manualmente:"
        echo -e "  ${CIANO}.venv/bin/pip install -r requirements.txt${RESET}"
        echo ""
    fi
}

instalar_base
criar_venv
instalar_requirements
instalar_desktop
criar_runner
verificar