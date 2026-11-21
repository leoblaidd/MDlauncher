"""Ponto de entrada do MD Launcher."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resource(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel


def main() -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QGuiApplication, QIcon
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME, __version__
    from .storage import data_dir
    from .ui import theme

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    if sys.platform.startswith("win"):
        try:  # ícone próprio na barra de tarefas
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("leoblaidd.MDLauncher")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("MDLauncher")
    f = QFont("Segoe UI")
    f.setPixelSize(13)
    app.setFont(f)

    check = data_dir() / "check.png"
    theme.pixmap("check", 14, "#ffffff", 1.0).save(str(check), "PNG")
    app.setStyleSheet(theme.QSS.replace(":/check", check.as_posix()))

    ico = resource("assets/icon.ico" if sys.platform.startswith("win") else "assets/icon.png")
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))

    from .ui.main_window import MainWindow
    w = MainWindow()
    w.show()
    w.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
