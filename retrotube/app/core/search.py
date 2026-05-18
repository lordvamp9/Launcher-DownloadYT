"""Búsqueda y descubrimiento de vídeos mediante ``yt-dlp`` (sin API key).

Modos soportados:
- ``query``        : búsqueda con ``ytsearch20:"..."``.
- ``trending``     : tendencias públicas de YouTube.
- ``recommended``  : feed personalizado (requiere cookies del navegador).
- ``playlist``     : extracción de los vídeos de una lista por URL.
"""
from __future__ import annotations

import json
import subprocess
from typing import Optional

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from app.core.downloader import ytdlp_base_command
from app.core.validators import InvalidYouTubeURL, validate_playlist_url

_TRENDING_URL = "https://www.youtube.com/feed/trending"
_RECOMMENDED_URL = "https://www.youtube.com/feed/recommended"


def _format_duration(seconds: object) -> str:
    """Convierte una duración en segundos a ``H:MM:SS`` o ``M:SS``."""
    try:
        total = int(float(seconds))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "--:--"
    if total <= 0:
        return "--:--"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def parse_entry(obj: dict) -> Optional[dict]:
    """Normaliza una entrada JSON de yt-dlp al modelo interno de la app.

    Devuelve ``None`` si la entrada no contiene un ID de vídeo utilizable.
    """
    video_id = obj.get("id") or ""
    if not video_id or len(video_id) != 11:
        return None
    duration = obj.get("duration")
    return {
        "id": video_id,
        "title": obj.get("title") or "(sin título)",
        "channel": obj.get("channel") or obj.get("uploader") or "Desconocido",
        "duration": int(duration) if isinstance(duration, (int, float)) else 0,
        "duration_text": _format_duration(duration),
        "view_count": int(obj.get("view_count") or 0),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        # Miniatura estable servida por el CDN de YouTube.
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


class SearchSignals(QObject):
    """Señales emitidas por una tarea de búsqueda."""

    results = pyqtSignal(str, list)   # modo, lista de vídeos
    error = pyqtSignal(str, str)      # modo, mensaje de error


class SearchTask(QRunnable):
    """Ejecuta una búsqueda/exploración de vídeos en segundo plano."""

    def __init__(
        self,
        mode: str,
        query: str = "",
        limit: int = 20,
        browser: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.query = query
        self.limit = max(1, min(40, limit))
        self.browser = browser
        self.proxy = proxy
        self.signals = SearchSignals()

    def _target(self) -> str:
        """Devuelve el argumento de destino que recibirá yt-dlp."""
        if self.mode == "query":
            # ytsearch evita por completo la necesidad de una API key.
            return f"ytsearch{self.limit}:{self.query}"
        if self.mode == "trending":
            return _TRENDING_URL
        if self.mode == "recommended":
            return _RECOMMENDED_URL
        if self.mode == "playlist":
            # Lanza InvalidYouTubeURL si la URL no es una lista legítima.
            return validate_playlist_url(self.query)
        raise ValueError(f"Modo de búsqueda desconocido: {self.mode!r}")

    def _build_command(self, target: str) -> list[str]:
        """Compone el comando de extracción de metadatos (sin descarga)."""
        cmd = ytdlp_base_command(self.browser, self.proxy)
        cmd += [
            "--flat-playlist",
            "--dump-json",
            "--no-download",
            "--playlist-end", str(self.limit),
            target,
        ]
        return cmd

    def run(self) -> None:
        """Ejecuta yt-dlp, interpreta su salida JSON y emite los resultados."""
        try:
            target = self._target()
        except (InvalidYouTubeURL, ValueError) as exc:
            self.signals.error.emit(self.mode, str(exc))
            return
        try:
            completed = subprocess.run(
                self._build_command(target),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except FileNotFoundError:
            self.signals.error.emit(
                self.mode, "No se encontró yt-dlp. Revisa la instalación."
            )
            return
        except subprocess.TimeoutExpired:
            self.signals.error.emit(
                self.mode, "La búsqueda superó el tiempo de espera (60 s)."
            )
            return
        except OSError as exc:
            self.signals.error.emit(self.mode, f"Error de proceso: {exc}")
            return

        videos: list[dict] = []
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                # Cada línea es un objeto JSON independiente (NDJSON).
                entry = parse_entry(json.loads(line))
            except json.JSONDecodeError:
                continue
            if entry is not None:
                videos.append(entry)

        if not videos and completed.returncode != 0:
            detail = (completed.stderr or "").strip().splitlines()
            msg = detail[-1] if detail else "No se obtuvieron resultados."
            self.signals.error.emit(self.mode, msg)
            return
        self.signals.results.emit(self.mode, videos)


if __name__ == "__main__":
    import sys

    from PyQt6.QtCore import QCoreApplication, QThreadPool

    # La consola de Windows (cp1252) no admite emojis: forzamos UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    app = QCoreApplication(sys.argv)

    def _on_results(mode: str, vids: list) -> None:
        print(f"[{mode}] {len(vids)} resultados")
        for video in vids:
            print(" -", video["title"])
        app.quit()

    def _on_error(mode: str, err: str) -> None:
        print(f"[{mode}] ERROR: {err}")
        app.quit()

    task = SearchTask("query", "lo-fi hip hop", limit=5)
    task.signals.results.connect(_on_results)
    task.signals.error.connect(_on_error)
    QThreadPool.globalInstance().start(task)
    sys.exit(app.exec())
