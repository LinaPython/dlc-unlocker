<div align="center">

# 🎮 DLC Unlocker
**Gerenciador gráfico de DLCs do The Sims 4 para Linux**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![Platform](https://img.shields.io/badge/Platform-Linux-orange?style=flat-square&logo=linux)
![License](https://img.shields.io/badge/License-As--is-gray?style=flat-square)

</div>

---

![Screenshot](https://i.imgur.com/qzyTwHG.png)

---

## O que é

DLC Unlocker é uma interface gráfica em Python para baixar, extrair e instalar DLCs do The Sims 4 no Linux. Também integra um gerenciador do EA App Unlocker para prefixes Wine, Steam, Lutris e Bottles.

---

## Funcionalidades

- Download direto via Mediafire com barra de progresso
- Filtro em tempo real por nome ou tipo de pacote
- Extração automática dos `.zip` com progresso por arquivo
- Movimentação das pastas extraídas para o local correto do jogo (detectado automaticamente via Steam)
- Gerenciador do EA Unlocker — instala, desinstala e abre a pasta de configs no prefix correto
- Splash screen configurável
- Logs persistentes em `logs/dlc_manager.log`
- Configuração salva entre sessões

---

## Requisitos

- Python 3.10 ou superior
- Steam com The Sims 4 instalado

### Dependências Python

| Pacote | Uso |
|---|---|
| `customtkinter` | Interface gráfica |
| `requests` | Downloads e resolução de links Mediafire |
| `beautifulsoup4` | Parsing HTML do Mediafire |
| `Pillow` | Splash screen e imagens |
| `curl-cffi` | Bypass do Cloudflare para Expansion Packs |
| `tkinter` | Backend gráfico (geralmente incluído no Python do sistema) |

> **Bazzite / Silverblue e outros sistemas imutáveis:** o `tkinter` precisa ser instalado via `rpm-ostree` — veja a seção [Sistemas Imutáveis](#sistemas-imutáveis-bazzite--silverblue) abaixo.

---

## Instalação

Clone o repositório e entre na pasta:

```bash
git clone https://github.com/seu-usuario/dlc-unlocker.git
cd dlc-unlocker
```

Dê permissão de execução ao script e rode:

```bash
chmod +x install.sh
./install.sh
```

O `install.sh` detecta sua distribuição automaticamente e instala todas as dependências:

| Distro | Gerenciador |
|---|---|
| Arch / Manjaro / EndeavourOS | `pacman` |
| Ubuntu / Debian / Mint / Pop!\_OS | `apt` |
| Fedora / RHEL / CentOS | `dnf` |
| openSUSE | `zypper` |
| Bazzite / Silverblue (imutáveis) | `pip` + `rpm-ostree` |

Após a instalação, o script verifica automaticamente se todas as dependências foram encontradas e exibe o resultado.

### Sistemas Imutáveis (Bazzite / Silverblue)

Em sistemas baseados em `rpm-ostree`, o `install.sh` instala os pacotes Python via `pip --user` automaticamente. O `tkinter` precisa ser instalado separadamente:

```bash
rpm-ostree install python3-tkinter
```

Reinicie o sistema após esse comando. Os demais pacotes são instalados via pip sem necessidade de reinicialização.

---

## Como usar

```bash
python3 main.py
```

### Fluxo recomendado

```
1. Escolha a pasta de destino dos downloads
2. Selecione os DLCs que quer baixar e clique em ⬇ Baixar
3. Após o download, clique em 📦 Extrair
4. Após a extração, clique em 📂 Mover
5. Use 🛠 EA Unlocker para ativar os DLCs no jogo
```

---

## Screenshots

| Interface principal | EA Unlocker | Extração |
|---|---|---|
| ![main](https://i.imgur.com/0rKU67W.png) | ![unlocker](https://i.imgur.com/17UNqjl.png) | ![zip](https://i.imgur.com/fAZd0B5.png) |

---

## Observações

- O cancelamento de download mantém o arquivo parcial no disco para retomada futura.
- A detecção da pasta do Sims 4 é automática via `libraryfolders.vdf` da Steam, incluindo bibliotecas externas.
- O EA Unlocker suporta prefixes de Wine nativo, Lutris, Bottles e Steam (Proton).
- Em caso de falha na instalação via pip, tente: `pip3 install --user customtkinter requests beautifulsoup4 Pillow curl-cffi`

---

<div align="center">

*A pirataria surge quando o valor de uma obra encontra a realidade de quem não pode alcançá-la.*

</div>
