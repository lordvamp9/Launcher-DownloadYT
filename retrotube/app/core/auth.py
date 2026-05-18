"""Gestión de sesión de YouTube mediante cookies del navegador.

Política de seguridad estricta:
- La autenticación se realiza SIEMPRE con ``--cookies-from-browser``.
- La aplicación NUNCA solicita usuario ni contraseña.
- NUNCA se guardan cookies, tokens ni datos de sesión en disco ni en SQLite.
- El "cierre de sesión" se limita a olvidar el estado en memoria y a vaciar
  la caché temporal de yt-dlp.
"""
from __future__ import annotations

import json
import subprocess
from typing import Optional

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from app.core.downloader import ytdlp_base_command

SUPPORTED_BROWSERS = ("chrome", "firefox", "edge", "brave", "opera", "vivaldi")

# El feed de historial exige sesión iniciada: es una sonda fiable de login.
_PROBE_URL = "https://www.youtube.com/feed/history"


class AuthSignals(QObject):
    """Señales emitidas por la verificación de sesión."""

    verified = pyqtSignal(bool, str)   # autenticado, nombre/estado
    error = pyqtSignal(str)            # mensaje de error


class AuthTask(QRunnable):
    """Comprueba en segundo plano si las cookies del navegador dan sesión."""

    def __init__(self, browser: str, proxy: Optional[str] = None) -> None:
        super().__init__()
        self.browser = browser
        self.proxy = proxy
        self.signals = AuthSignals()

    def _build_command(self) -> list[str]:
        """Comando de sondeo: extrae 1 elemento del feed de historial."""
        cmd = ytdlp_base_command(self.browser, self.proxy)
        cmd += [
            "--flat-playlist",
            "--dump-json",
            "--playlist-end", "1",
            "--no-download",
            _PROBE_URL,
        ]
        return cmd

    def run(self) -> None:
        """Ejecuta la sonda y emite el resultado de la verificación."""
        try:
            completed = subprocess.run(
                self._build_command(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=45,
            )
        except FileNotFoundError:
            self.signals.error.emit("No se encontró yt-dlp.")
            return
        except subprocess.TimeoutExpired:
            self.signals.error.emit("La verificación superó el tiempo límite.")
            return
        except OSError as exc:
            self.signals.error.emit(f"Error al verificar la sesión: {exc}")
            return

        # Si el historial devuelve algún elemento, la sesión está activa.
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("id"):
                name = obj.get("channel") or "Usuario autenticado"
                self.signals.verified.emit(True, name)
                return

        # Sin elementos => sin sesión (o cookies no extraíbles del navegador).
        stderr = (completed.stderr or "").lower()
        if "could not find" in stderr or "unable to find" in stderr:
            self.signals.error.emit(
                f"No se pudieron leer las cookies de {self.browser}."
            )
            return
        self.signals.verified.emit(False, "Sin sesión")


class AuthManager(QObject):
    """Mantiene el estado de sesión y expone operaciones de login/logout."""

    auth_changed = pyqtSignal(bool, str)   # autenticado, nombre/estado
    auth_error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._authenticated = False
        self._channel = "Sin sesión"
        self._browser = "chrome"

    @property
    def authenticated(self) -> bool:
        """Indica si hay una sesión activa verificada."""
        return self._authenticated

    @property
    def channel(self) -> str:
        """Nombre/estado de la cuenta autenticada."""
        return self._channel

    @property
    def browser(self) -> str:
        """Navegador seleccionado como origen de cookies."""
        return self._browser

    def set_browser(self, browser: str) -> None:
        """Define el navegador del que se leerán las cookies."""
        if browser in SUPPORTED_BROWSERS:
            self._browser = browser

    def verify(self, proxy: Optional[str] = None) -> None:
        """Lanza la verificación asíncrona de la sesión."""
        task = AuthTask(self._browser, proxy)
        task.signals.verified.connect(self._on_verified)
        task.signals.error.connect(self._on_error)
        QThreadPool.globalInstance().start(task)

    def logout(self) -> None:
        """Cierra la sesión: olvida el estado y vacía la caché de yt-dlp.

        No existe ninguna tabla de sesión en SQLite porque, por diseño, jamás
        se persisten datos de sesión. Aquí solo se limpia la caché temporal.
        """
        self._authenticated = False
        self._channel = "Sin sesión"
        try:
            subprocess.run(
                ytdlp_base_command() + ["--rm-cache-dir"],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            # El fallo al limpiar la caché no debe impedir el cierre de sesión.
            pass
        self.auth_changed.emit(False, self._channel)

    def _on_verified(self, authenticated: bool, name: str) -> None:
        self._authenticated = authenticated
        self._channel = name if authenticated else "Sin sesión"
        self.auth_changed.emit(self._authenticated, self._channel)

    def _on_error(self, message: str) -> None:
        self._authenticated = False
        self._channel = "Sin sesión"
        self.auth_error.emit(message)
        self.auth_changed.emit(False, self._channel)


if __name__ == "__main__":
    import sys

    from PyQt6.QtCore import QCoreApplication

    app = QCoreApplication(sys.argv)
    manager = AuthManager()
    manager.set_browser("chrome")
    manager.auth_changed.connect(
        lambda ok, name: (print(f"Autenticado={ok} · {name}"), app.quit())
    )
    manager.auth_error.connect(lambda msg: print("Aviso:", msg))
    manager.verify()
    sys.exit(app.exec())
