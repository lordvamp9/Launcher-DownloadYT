"""RetroTube Downloader - punto de entrada de la aplicación.

Arranque:
1. Genera el ``.gitignore`` si es el primer arranque.
2. Carga la hoja de estilos global.
3. Muestra el splash animado (~2,5 s).
4. Transición con deslizamiento hacia arriba y apertura del dashboard.

Ejecución:  ``python main.py``
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from app import __app_name__
from app.ui.main_window import MainWindow
from app.ui.splash import SplashScreen
from app.utils.animations import slide_up_out
from app.utils.security import ensure_gitignore

# Raíz del proyecto: carpeta que contiene este archivo.
_PROJECT_ROOT = Path(__file__).resolve().parent


def _load_stylesheet(app: QApplication) -> None:
    """Carga ``style.qss`` y lo aplica a toda la aplicación."""
    qss_path = _PROJECT_ROOT / "app" / "ui" / "style.qss"
    if qss_path.is_file():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def main() -> int:
    """Inicializa Qt, muestra el splash y lanza la ventana principal."""
    # Genera el .gitignore en el primer arranque si aún no existe.
    ensure_gitignore(_PROJECT_ROOT)

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    _load_stylesheet(app)

    splash = SplashScreen()
    window = MainWindow()

    def _show_main() -> None:
        """Transición del splash al dashboard tras la animación de arranque."""
        slide_up_out(splash, distance=80, duration=420)
        # La ventana principal aparece cuando el splash termina de salir.
        QTimer.singleShot(380, window.show)
        QTimer.singleShot(820, splash.close)

    splash.finished.connect(_show_main)
    splash.show()
    splash.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
