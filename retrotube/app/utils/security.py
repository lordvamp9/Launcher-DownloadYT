"""Utilidades de seguridad: rutas de datos, permisos y archivos temporales.

Principios:
- Nunca se almacenan credenciales, tokens ni sesiones en disco.
- Los archivos de cookies (si llegasen a crearse) son temporales y se
  eliminan siempre en un bloque ``finally``.
- ``settings.json`` recibe permisos restrictivos (600) cuando el SO lo permite.
"""
from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Iterator

APP_DIR_NAME = ".retrotube"

# Líneas mínimas que debe contener el .gitignore generado al primer arranque.
_GITIGNORE_LINES = (
    "*.db",
    "settings.json",
    "cookies*.txt",
    "*.log",
    "__pycache__/",
    "*.pyc",
    ".venv/",
    "build/",
    "dist/",
)


def app_data_dir() -> Path:
    """Devuelve el directorio de datos de la app, creándolo si no existe."""
    base = Path.home() / APP_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def thumbnails_dir() -> Path:
    """Directorio de caché de miniaturas descargadas."""
    directory = app_data_dir() / "thumbnails"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def database_path() -> Path:
    """Ruta del archivo SQLite local."""
    return app_data_dir() / "retrotube.db"


def settings_path() -> Path:
    """Ruta del archivo de configuración JSON."""
    return app_data_dir() / "settings.json"


def log_path() -> Path:
    """Ruta del archivo de log de la aplicación."""
    return app_data_dir() / "retrotube.log"


def secure_file(path: Path) -> None:
    """Aplica permisos 600 (solo propietario) cuando el SO lo soporta.

    En Windows ``chmod`` tiene efecto limitado; se ignora cualquier error
    porque la ausencia de permisos POSIX no debe abortar la aplicación.
    """
    with contextlib.suppress(OSError, NotImplementedError):
        os.chmod(path, 0o600)


@contextlib.contextmanager
def temporary_cookie_file() -> Iterator[Path]:
    """Crea un archivo de cookies temporal y garantiza su borrado.

    El archivo se elimina SIEMPRE en el bloque ``finally``, incluso si se
    produce una excepción durante su uso.
    """
    fd, name = tempfile.mkstemp(prefix="cookies_", suffix=".txt")
    os.close(fd)
    path = Path(name)
    secure_file(path)
    try:
        yield path
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


def ensure_gitignore(project_root: Path) -> Path:
    """Genera ``.gitignore`` en la raíz del proyecto si aún no existe.

    Devuelve la ruta del archivo (creado o preexistente).
    """
    gitignore = project_root / ".gitignore"
    if not gitignore.exists():
        content = "\n".join(_GITIGNORE_LINES) + "\n"
        gitignore.write_text(content, encoding="utf-8")
    return gitignore


if __name__ == "__main__":
    print("Directorio de datos:", app_data_dir())
    print("Miniaturas:", thumbnails_dir())
    print("Base de datos:", database_path())
    print("Configuración:", settings_path())
    with temporary_cookie_file() as cookie:
        print("Cookie temporal creada:", cookie, "->", cookie.exists())
    print("Cookie eliminada tras el contexto:", not cookie.exists())
