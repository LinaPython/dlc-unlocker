# --- main.py ---
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from PySide6.QtWidgets import QApplication
from core.config import carregar_config
from gui import theme as _theme


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("DLC Unlocker")
    app.setApplicationVersion("2.0.0")

    cfg = carregar_config()
    _theme.apply(app, cfg.get("tema", "black"))

    from gui.splash import deve_mostrar_splash, SplashScreen
    from gui.app import MainWindow

    if deve_mostrar_splash():
        splash = SplashScreen(
            imagem=BASE_DIR / "assets" / "__.jpeg",
            texto=(
                "A pirataria surge quando o valor de uma obra\n"
                "encontra a realidade de quem nao pode alcanca-la.\n\n"
                "pirateie TUDO que voce puder!"
            ),
        )
        splash.show()
    else:
        window = MainWindow()
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()