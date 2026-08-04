#!/bin/bash
# ============================================================
#  Suporta: Arch, Debian/Ubuntu, Fedora/RHEL, openSUSE, Bazzite
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

echo ""
echo -e "${CIANO}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CIANO}║       DLC Unlocker — Setup               ║${RESET}"
echo -e "${CIANO}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ── Detecta distro ─────────────────────────────────────────
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO_ID="${ID}"
    DISTRO_LIKE="${ID_LIKE:-}"
    DISTRO_VARIANT="${VARIANT_ID:-}"
else
    erro "Não foi possível detectar a distribuição Linux."
fi

info "Distribuição: ${PRETTY_NAME:-$DISTRO_ID}"

# ── Detecta distros imutáveis ────────────────────
# Bazzite e similares usam rpm-ostree
# e bloqueiam o dnf para pacotes do sistema.
IMUTAVEL=false
if command -v rpm-ostree &>/dev/null; then
    IMUTAVEL=true
    aviso "Sistema imutável detectado (rpm-ostree). Usando pip para dependências Python."
fi

# ── Instala dependências por distro ────────────────────────
instalar_sistema() {
    # Arch / Manjaro / EndeavourOS
    if echo "${DISTRO_ID} ${DISTRO_LIKE}" | grep -qi "arch"; then
        info "Usando pacman..."
        sudo pacman -Sy --noconfirm --needed \
            python \
            python-pip \
            python-requests \
            python-beautifulsoup4 \
            python-pillow \
            tk

    # Bazzite (imutáveis baseados em Fedora)
    elif $IMUTAVEL; then
        info "Sistema imutável — pulando instalação via dnf."
        info "Instalando dependências Python via pip..."
        pip3 install --user \
            requests \
            beautifulsoup4 \
            customtkinter \
            Pillow \
            || pip3 install \
                requests \
                beautifulsoup4 \
                customtkinter \
                Pillow
        ok "Dependências Python instaladas via pip."

        # Verifica tkinter 
        if ! python3 -c "import tkinter" 2>/dev/null; then
            aviso "tkinter não encontrado."
            info "No Bazzite/Silverblue, instale via:"
            echo ""
            echo "  rpm-ostree install python3-tkinter"
            echo "  (reinicie após a instalação)"
            echo ""
        fi
        return

    # Debian / Ubuntu / Mint / Pop!_OS
    elif echo "${DISTRO_ID} ${DISTRO_LIKE}" | grep -qi "debian\|ubuntu"; then
        info "Usando apt..."
        sudo apt-get update -qq
        sudo apt-get install -y \
            python3 \
            python3-pip \
            python3-tk \
            python3-requests \
            python3-bs4 \
            python3-pil \
            python3-pil.imagetk

    # Fedora (não imutável)
    elif echo "${DISTRO_ID} ${DISTRO_LIKE}" | grep -qi "fedora\|rhel\|centos"; then
        info "Usando dnf..."
        sudo dnf install -y \
            python3 \
            python3-pip \
            python3-tkinter \
            python3-requests \
            python3-beautifulsoup4 \
            python3-pillow \
            python3-pillow-tk

    # openSUSE
    elif echo "${DISTRO_ID} ${DISTRO_LIKE}" | grep -qi "suse\|opensuse"; then
        info "Usando zypper..."
        sudo zypper install -y \
            python3 \
            python3-pip \
            python3-tk \
            python3-requests \
            python3-beautifulsoup4 \
            python3-Pillow

    else
        aviso "Distro '${DISTRO_ID}' não reconhecida. Tentando via pip..."
    fi
}

# ── Instala dependências Python via pip (complementar) ─────
instalar_pip() {
    info "Verificando pacotes Python via pip..."

    PKGS=()
    python3 -c "import customtkinter" 2>/dev/null || PKGS+=(customtkinter)
    python3 -c "import requests"      2>/dev/null || PKGS+=(requests)
    python3 -c "import bs4"           2>/dev/null || PKGS+=(beautifulsoup4)
    python3 -c "from PIL import Image, ImageTk" 2>/dev/null || PKGS+=(Pillow)

    if [ ${#PKGS[@]} -eq 0 ]; then
        ok "Todos os pacotes Python já estão instalados."
        return
    fi

    info "Instalando via pip: ${PKGS[*]}"
    pip3 install --user "${PKGS[@]}" 2>/dev/null \
        || pip3 install "${PKGS[@]}" --break-system-packages 2>/dev/null \
        || pip3 install "${PKGS[@]}" \
        || erro "Falha ao instalar pacotes pip."
}

# ── Verificações finais ────────────────────────────────────
verificar() {
    local ok_count=0
    local fail_count=0

    check() {
        local label="$1"
        local cmd="$2"
        if python3 -c "$cmd" 2>/dev/null; then
            ok "$label"
            ((ok_count++))
        else
            aviso "$label — NÃO encontrado"
            ((fail_count++))
        fi
    }

    echo ""
    info "Verificando dependências..."
    check "Python 3"        "import sys; assert sys.version_info >= (3,10)"
    check "tkinter"         "import tkinter"
    check "customtkinter"   "import customtkinter"
    check "requests"        "import requests"
    check "BeautifulSoup4"  "import bs4"
    check "Pillow (PIL)"    "from PIL import Image"
    check "Pillow (ImageTk)" "from PIL import ImageTk"

    echo ""
    if [ $fail_count -eq 0 ]; then
        ok "Todas as dependências estão instaladas! ($ok_count / $((ok_count + fail_count)))"
    else
        aviso "$fail_count dependência(s) não encontrada(s)."
        echo ""
        echo -e "  Se estiver no ${AMARELO}Bazzite / Silverblue${RESET}, execute:"
        echo -e "  ${CIANO}rpm-ostree install python3-tkinter${RESET}"
        echo -e "  e reinicie o sistema."
        echo ""
        echo -e "  Para os demais pacotes:"
        echo -e "  ${CIANO}pip3 install --user customtkinter requests beautifulsoup4 Pillow${RESET}"
    fi
}

# ── Execução ───────────────────────────────────────────────
instalar_sistema
instalar_pip
verificar

echo ""
echo -e "  Para iniciar o app:"
echo -e "  ${CIANO}python3 main.py${RESET}"
echo ""