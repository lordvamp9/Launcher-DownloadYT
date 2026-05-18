"""RetroTube Downloader - punto de entrada de la aplicación.

Arranque:
1. Genera el ``.gitignore`` si es el primer arranque (solo en modo script).
2. Carga la hoja de estilos y el icono de la aplicación.
3. Muestra el splash animado (~2,5 s).
4. Transición con deslizamiento hacia arriba y apertura del dashboard.

Ejecución:  ``python main.py``
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app import __app_name__
from app.ui.main_window import MainWindow
from app.ui.splash import SplashScreen
from app.utils.animations import slide_up_out
from app.utils.security import ensure_gitignore

# Indica si la aplicación se está ejecutando empaquetada como .exe.
_FROZEN = getattr(sys, "frozen", False)


def _resource_root() -> Path:
    """Raíz de recursos: carpeta temporal del .exe o carpeta del proyecto."""
    if _FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


_PROJECT_ROOT = _resource_root()


def _load_stylesheet(app: QApplication) -> None:
    """Carga ``style.qss`` y lo aplica a toda la aplicación."""
    qss_path = _PROJECT_ROOT / "app" / "ui" / "style.qss"
    if qss_path.is_file():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def _app_icon() -> QIcon:
    """Devuelve el icono de la aplicación (konata.ico)."""
    icon_path = _PROJECT_ROOT / "konata.ico"
    return QIcon(str(icon_path)) if icon_path.is_file() else QIcon()


def _set_taskbar_identity() -> None:
    """Asigna un AppUserModelID propio para que Windows agrupe el icono.

    Sin esto la barra de tareas mostraría el icono genérico de Python.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "RetroTube.Downloader.v1"
        )
    except (OSError, AttributeError):
        # Si la llamada no está disponible, la app sigue funcionando igual.
        pass


def main() -> int:
    """Inicializa Qt, muestra el splash y lanza la ventana principal."""
    # El .gitignore solo tiene sentido al ejecutar desde el código fuente.
    if not _FROZEN:
        ensure_gitignore(_PROJECT_ROOT)

    _set_taskbar_identity()

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    _load_stylesheet(app)

    icon = _app_icon()
    app.setWindowIcon(icon)

    splash = SplashScreen()
    splash.setWindowIcon(icon)
    window = MainWindow()
    window.setWindowIcon(icon)

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
