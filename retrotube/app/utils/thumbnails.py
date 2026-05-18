"""Descarga asíncrona y caché de miniaturas con ``httpx`` + ``QThreadPool``.

Las miniaturas se guardan en la carpeta de caché de la aplicación usando el
ID del vídeo como nombre de archivo. Las descargas se hacen en hilos para no
bloquear nunca la interfaz, y todas las peticiones HTTP llevan timeouts
estrictos.
"""
from __future__ import annotations

from pathlib import Path

import httpx
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from app.utils.security import thumbnails_dir

# Timeout estricto: conexión + lectura limitadas para evitar cuelgues.
_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
_MAX_BYTES = 4 * 1024 * 1024  # Límite defensivo de 4 MB por miniatura.


def cached_path(video_id: str) -> Path:
    """Ruta en caché que correspondería a la miniatura de un vídeo."""
    safe = "".join(c for c in video_id if c.isalnum() or c in "-_")
    return thumbnails_dir() / f"{safe}.jpg"


class ThumbnailSignals(QObject):
    """Señales emitidas por una tarea de descarga de miniatura."""

    loaded = pyqtSignal(str, str)   # video_id, ruta local
    failed = pyqtSignal(str, str)   # video_id, mensaje de error


class ThumbnailTask(QRunnable):
    """Descarga una miniatura concreta en segundo plano."""

    def __init__(self, video_id: str, url: str) -> None:
        super().__init__()
        self.video_id = video_id
        self.url = url
        self.signals = ThumbnailSignals()

    def run(self) -> None:
        """Descarga la imagen y la guarda en la caché local."""
        destination = cached_path(self.video_id)
        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as cli:
                response = cli.get(self.url)
                response.raise_for_status()
                content = response.content
        except httpx.HTTPError as exc:
            self.signals.failed.emit(self.video_id, f"HTTP: {exc}")
            return
        except OSError as exc:
            self.signals.failed.emit(self.video_id, f"Red: {exc}")
            return

        if not content or len(content) > _MAX_BYTES:
            self.signals.failed.emit(self.video_id, "Miniatura inválida.")
            return
        try:
            destination.write_bytes(content)
        except OSError as exc:
            self.signals.failed.emit(self.video_id, f"Disco: {exc}")
            return
        self.signals.loaded.emit(self.video_id, str(destination))


class ThumbnailManager(QObject):
    """Coordina la obtención de miniaturas con caché en disco."""

    thumbnail_ready = pyqtSignal(str, str)   # video_id, ruta local

    def __init__(self) -> None:
        super().__init__()
        self._pool = QThreadPool.globalInstance()
        self._pending: set[str] = set()

    def request(self, video_id: str, url: str) -> None:
        """Solicita una miniatura; usa la caché si ya está descargada."""
        if not video_id or not url:
            return
        existing = cached_path(video_id)
        if existing.is_file() and existing.stat().st_size > 0:
            # Cacheada: respuesta inmediata sin tocar la red.
            self.thumbnail_ready.emit(video_id, str(existing))
            return
        if video_id in self._pending:
            return
        self._pending.add(video_id)
        task = ThumbnailTask(video_id, url)
        task.signals.loaded.connect(self._on_loaded)
        task.signals.failed.connect(self._on_failed)
        self._pool.start(task)

    def _on_loaded(self, video_id: str, path: str) -> None:
        self._pending.discard(video_id)
        self.thumbnail_ready.emit(video_id, path)

    def _on_failed(self, video_id: str, _message: str) -> None:
        # Se descarta el pendiente; la tarjeta conservará su marcador genérico.
        self._pending.discard(video_id)


if __name__ == "__main__":
    import sys

    from PyQt6.QtCore import QCoreApplication

    app = QCoreApplication(sys.argv)
    manager = ThumbnailManager()
    manager.thumbnail_ready.connect(
        lambda vid, path: (print(f"Lista {vid}: {path}"), app.quit())
    )
    manager.request(
        "dQw4w9WgXcQ",
        "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
    )
    sys.exit(app.exec())
