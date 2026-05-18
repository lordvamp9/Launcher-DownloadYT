"""Motor de descargas basado en ``yt-dlp`` (subproceso) + ``QThreadPool``.

Decisiones de seguridad:
- ``yt-dlp`` se invoca SIEMPRE como ``[python, -m, yt_dlp, ...]`` con una
  lista de argumentos; nunca ``shell=True``.
- Toda URL pasa por :func:`validate_youtube_url` antes de usarse.
- La autenticación se delega a ``--cookies-from-browser``: las cookies se
  leen en memoria y jamás se escriben en disco desde la aplicación.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from app.core.validators import validate_youtube_url

# Delimitador interno usado en las plantillas de salida de yt-dlp.
_SEP = "¦"  # Carácter raro, improbable en títulos o rutas.
_PROG_TAG = "RETRO_PROG"
_FILE_TAG = "RETRO_FILE"

_PROGRESS_TEMPLATE = (
    f"download:{_PROG_TAG}{_SEP}%(progress._percent_str)s{_SEP}"
    f"%(progress._speed_str)s{_SEP}%(progress._eta_str)s"
)
_PRINT_TEMPLATE = f"after_move:{_FILE_TAG}{_SEP}%(filepath)s"

# Mapa de calidad -> altura máxima de vídeo.
_HEIGHTS = {
    "144": 144, "240": 240, "360": 360, "480": 480,
    "720": 720, "1080": 1080, "1440": 1440, "2160": 2160,
}

QUALITY_CHOICES = (
    "144", "240", "360", "480", "720", "1080", "1440", "2160",
    "audio_mp3", "audio_opus",
)


def ytdlp_program() -> list[str]:
    """Devuelve el ejecutable de yt-dlp adecuado al contexto.

    - En modo empaquetado (.exe) ``sys.executable`` ya no es un intérprete
      de Python, así que se usa el ``yt-dlp.exe`` incluido en el paquete.
    - En modo normal se invoca el módulo ``yt_dlp`` del entorno de Python.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        bundled = base / "yt-dlp.exe"
        if bundled.is_file():
            return [str(bundled)]
    return [sys.executable, "-m", "yt_dlp"]


def ytdlp_base_command(
    browser: Optional[str] = None,
    proxy: Optional[str] = None,
) -> list[str]:
    """Construye el prefijo común de todo comando ``yt-dlp``."""
    cmd = ytdlp_program() + ["--ignore-config", "--no-warnings"]
    if browser:
        # Las cookies se leen del navegador en memoria, nunca se almacenan.
        cmd += ["--cookies-from-browser", browser]
    if proxy:
        cmd += ["--proxy", proxy]
    return cmd


def ffmpeg_location() -> Optional[str]:
    """Devuelve la carpeta de ffmpeg incluida con la app, si existe.

    yt-dlp necesita ffmpeg para fusionar vídeo + audio y para extraer audio
    (MP3/OPUS). Si no se encuentra una copia incluida, se devuelve ``None`` y
    yt-dlp recurrirá al ffmpeg disponible en el PATH del sistema.
    """
    folders: list[Path] = []
    if getattr(sys, "frozen", False):
        folders.append(Path(getattr(sys, "_MEIPASS", ".")))
        folders.append(Path(sys.executable).parent)
    else:
        # En modo script: raíz del proyecto (dos niveles por encima).
        folders.append(Path(__file__).resolve().parents[2])
    for folder in folders:
        if (folder / "ffmpeg.exe").is_file() or (folder / "ffmpeg").is_file():
            return str(folder)
    return None


def build_format_args(quality: str, container: str) -> list[str]:
    """Traduce una calidad lógica a los argumentos de formato de yt-dlp."""
    if quality == "audio_mp3":
        return ["-x", "--audio-format", "mp3", "-f", "bestaudio/best"]
    if quality == "audio_opus":
        return ["-x", "--audio-format", "opus", "-f", "bestaudio/best"]
    height = _HEIGHTS.get(quality, 1080)
    selector = f"bv*[height<={height}]+ba/b[height<={height}]"
    merge = container if container in ("mp4", "mkv", "webm") else "mp4"
    return ["-f", selector, "--merge-output-format", merge]


class DownloadSignals(QObject):
    """Señales emitidas por una tarea de descarga."""

    started = pyqtSignal(str)                  # task_id
    progress = pyqtSignal(str, float, str, str)  # task_id, %, velocidad, ETA
    finished = pyqtSignal(str, str, int)       # task_id, ruta, tamaño_bytes
    failed = pyqtSignal(str, str)              # task_id, mensaje de error


class DownloadTask(QRunnable):
    """Descarga un único vídeo en un hilo del pool."""

    def __init__(
        self,
        task_id: str,
        url: str,
        output_dir: str,
        quality: str,
        container: str = "mp4",
        browser: Optional[str] = None,
        proxy: Optional[str] = None,
        rate_limit: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.task_id = task_id
        # La validación protege frente a URLs maliciosas o locales.
        self.url = validate_youtube_url(url)
        self.output_dir = output_dir
        self.quality = quality
        self.container = container
        self.browser = browser
        self.proxy = proxy
        self.rate_limit = rate_limit
        self.signals = DownloadSignals()
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False

    def cancel(self) -> None:
        """Solicita la cancelación y termina el subproceso si está activo."""
        self._cancelled = True
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def _build_command(self) -> list[str]:
        """Compone la lista de argumentos completa para yt-dlp."""
        cmd = ytdlp_base_command(self.browser, self.proxy)
        cmd += build_format_args(self.quality, self.container)
        cmd += [
            "--no-playlist",
            "--newline",
            "--no-color",
            "--progress-template", _PROGRESS_TEMPLATE,
            "--print", _PRINT_TEMPLATE,
            "-o", os.path.join(self.output_dir, "%(title)s [%(id)s].%(ext)s"),
        ]
        if self.rate_limit:
            cmd += ["--limit-rate", self.rate_limit]
        ffmpeg = ffmpeg_location()
        if ffmpeg:
            # Permite remux y extracción de audio sin depender del PATH.
            cmd += ["--ffmpeg-location", ffmpeg]
        cmd.append(self.url)
        return cmd

    def _emit_progress(self, line: str) -> None:
        """Interpreta una línea de progreso de yt-dlp y emite la señal."""
        parts = line.split(_SEP)
        if len(parts) != 4:
            return
        _, percent_raw, speed, eta = parts
        match = re.search(r"[\d.]+", percent_raw)
        percent = float(match.group()) if match else 0.0
        self.signals.progress.emit(
            self.task_id, percent, speed.strip() or "--", eta.strip() or "--"
        )

    def run(self) -> None:  # noqa: C901 - bucle de lectura de salida.
        """Ejecuta la descarga; método invocado por el QThreadPool."""
        os.makedirs(self.output_dir, exist_ok=True)
        self.signals.started.emit(self.task_id)
        final_path = ""
        try:
            self._process = subprocess.Popen(
                self._build_command(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert self._process.stdout is not None
            for raw in self._process.stdout:
                line = raw.rstrip("\n")
                if line.startswith(_PROG_TAG):
                    self._emit_progress(line)
                elif line.startswith(_FILE_TAG):
                    final_path = line.split(_SEP, 1)[-1].strip()
            return_code = self._process.wait()
        except FileNotFoundError:
            self.signals.failed.emit(
                self.task_id, "No se encontró yt-dlp. Revisa la instalación."
            )
            return
        except OSError as exc:
            self.signals.failed.emit(self.task_id, f"Error de proceso: {exc}")
            return

        if self._cancelled:
            self.signals.failed.emit(self.task_id, "Descarga cancelada.")
            return
        if return_code != 0:
            self.signals.failed.emit(
                self.task_id, f"yt-dlp terminó con código {return_code}."
            )
            return

        size = 0
        if final_path and os.path.isfile(final_path):
            try:
                size = os.path.getsize(final_path)
            except OSError:
                size = 0
        self.signals.finished.emit(self.task_id, final_path, size)


class DownloadManager(QObject):
    """Coordina las descargas concurrentes mediante un ``QThreadPool``."""

    task_started = pyqtSignal(str)
    task_progress = pyqtSignal(str, float, str, str)
    task_finished = pyqtSignal(str, str, int)
    task_failed = pyqtSignal(str, str)

    def __init__(self, max_concurrent: int = 3) -> None:
        super().__init__()
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(max(1, min(5, max_concurrent)))
        self._tasks: dict[str, DownloadTask] = {}

    def set_max_concurrent(self, value: int) -> None:
        """Ajusta el número de descargas simultáneas (entre 1 y 5)."""
        self._pool.setMaxThreadCount(max(1, min(5, value)))

    def enqueue(self, task: DownloadTask) -> None:
        """Encola una tarea de descarga y reenvía sus señales."""
        self._tasks[task.task_id] = task
        task.signals.started.connect(self.task_started)
        task.signals.progress.connect(self.task_progress)
        task.signals.finished.connect(self._on_finished)
        task.signals.failed.connect(self._on_failed)
        self._pool.start(task)

    def cancel(self, task_id: str) -> None:
        """Cancela una tarea concreta por su identificador."""
        task = self._tasks.get(task_id)
        if task is not None:
            task.cancel()

    def cancel_all(self) -> None:
        """Cancela todas las descargas activas (uso al cerrar la app)."""
        for task in list(self._tasks.values()):
            task.cancel()

    def _on_finished(self, task_id: str, path: str, size: int) -> None:
        self._tasks.pop(task_id, None)
        self.task_finished.emit(task_id, path, size)

    def _on_failed(self, task_id: str, message: str) -> None:
        self._tasks.pop(task_id, None)
        self.task_failed.emit(task_id, message)


if __name__ == "__main__":
    print("Comando base:", ytdlp_base_command("chrome"))
    print("Formato 1080p:", build_format_args("1080", "mkv"))
    print("Formato audio:", build_format_args("audio_mp3", "mp4"))
