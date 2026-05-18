"""Validación estricta de URLs de YouTube.

Toda URL introducida por el usuario DEBE pasar por estas funciones antes de
entregarse a ``yt-dlp``. Así se evita que rutas locales, esquemas peligrosos
o dominios arbitrarios lleguen al subproceso.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

# Identificador de vídeo de YouTube: 11 caracteres del alfabeto base64-url.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Identificador de lista de reproducción: prefijo conocido + cuerpo.
_PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{12,42}$")

# Hosts admitidos para vídeos y listas de YouTube.
_ALLOWED_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
     "youtu.be", "www.youtu.be"}
)


class InvalidYouTubeURL(ValueError):
    """Se lanza cuando una URL no supera la validación."""


def _check_scheme_and_host(parsed) -> None:
    """Verifica que el esquema sea http(s) y el host esté en la lista blanca."""
    if parsed.scheme not in ("http", "https"):
        raise InvalidYouTubeURL(f"Esquema no permitido: {parsed.scheme!r}")
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        raise InvalidYouTubeURL(f"Dominio no permitido: {host!r}")


def extract_video_id(url: str) -> str | None:
    """Extrae el ID de vídeo de una URL o devuelve ``None`` si no lo contiene."""
    if not isinstance(url, str):
        return None
    candidate = url.strip()
    # Caso 1: el usuario pega directamente un ID de 11 caracteres.
    if _VIDEO_ID_RE.match(candidate):
        return candidate
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host in ("youtu.be", "www.youtu.be"):
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid if _VIDEO_ID_RE.match(vid) else None
    if host in _ALLOWED_HOSTS:
        # URL tipo /watch?v=ID
        query = parse_qs(parsed.query)
        if "v" in query and _VIDEO_ID_RE.match(query["v"][0]):
            return query["v"][0]
        # URLs tipo /shorts/ID, /embed/ID o /live/ID
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) == 2 and parts[0] in ("shorts", "embed", "live"):
            return parts[1] if _VIDEO_ID_RE.match(parts[1]) else None
    return None


def extract_playlist_id(url: str) -> str | None:
    """Extrae el ID de una lista de reproducción o devuelve ``None``."""
    if not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        return None
    query = parse_qs(parsed.query)
    if "list" in query:
        plist = query["list"][0]
        return plist if _PLAYLIST_ID_RE.match(plist) else None
    return None


def validate_youtube_url(url: str) -> str:
    """Valida una URL de vídeo y devuelve su forma canónica.

    Levanta :class:`InvalidYouTubeURL` si la URL no corresponde a un vídeo
    de YouTube reconocible.
    """
    if not url or not isinstance(url, str):
        raise InvalidYouTubeURL("La URL está vacía o no es texto.")
    video_id = extract_video_id(url)
    if video_id is None:
        # Si parece una URL http válida la analizamos para dar un error claro.
        with_scheme = url if "://" in url else f"https://{url}"
        try:
            _check_scheme_and_host(urlparse(with_scheme))
        except InvalidYouTubeURL:
            raise
        raise InvalidYouTubeURL("No se encontró un ID de vídeo válido.")
    return f"https://www.youtube.com/watch?v={video_id}"


def validate_playlist_url(url: str) -> str:
    """Valida una URL de lista de reproducción y devuelve su forma canónica."""
    if not url or not isinstance(url, str):
        raise InvalidYouTubeURL("La URL está vacía o no es texto.")
    playlist_id = extract_playlist_id(url)
    if playlist_id is None:
        raise InvalidYouTubeURL("No se encontró un ID de lista válido.")
    return f"https://www.youtube.com/playlist?list={playlist_id}"


if __name__ == "__main__":
    _tests = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=10",
        "dQw4w9WgXcQ",
        "file:///etc/passwd",
        "https://evil.com/watch?v=dQw4w9WgXcQ",
    ]
    for _t in _tests:
        try:
            print(f"OK   {_t!r:55} -> {validate_youtube_url(_t)}")
        except InvalidYouTubeURL as exc:
            print(f"FAIL {_t!r:55} -> {exc}")
