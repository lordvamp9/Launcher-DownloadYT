"""Pantalla de búsqueda y tarjeta de vídeo reutilizable.

La búsqueda usa ``ytsearch20`` de yt-dlp, sin necesidad de API key. Las
tarjetas resultantes admiten arrastrar y soltar hacia las listas locales.
"""
from __future__ import annotations

import json
from typing import Optional

from PyQt6.QtCore import (
    QEasingCurve,
    QMimeData,
    QPropertyAnimation,
    QRect,
    Qt,
    QThreadPool,
    pyqtSignal,
)
from PyQt6.QtGui import QDrag, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.search import SearchTask
from app.utils.animations import fade_in

# Tipo MIME propio para transportar vídeos en operaciones de arrastre.
VIDEO_MIME = "application/x-retrotube-video"

# Etiquetas legibles para el selector de calidad.
_QUALITY_LABELS = (
    ("144", "144p"), ("240", "240p"), ("360", "360p"), ("480", "480p"),
    ("720", "720p HD"), ("1080", "1080p FHD"), ("1440", "1440p QHD"),
    ("2160", "2160p 4K"), ("audio_mp3", "Audio MP3"),
    ("audio_opus", "Audio OPUS"),
)


def _format_views(count: int) -> str:
    """Formatea un número de vistas de forma compacta (K/M)."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M vistas"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K vistas"
    return f"{count} vistas"


class VideoCard(QFrame):
    """Tarjeta de un vídeo: miniatura, datos y controles de descarga.

    Se usa tanto en la rejilla del buscador como en el feed del dashboard.
    Es origen de arrastre (QDrag) para poder soltarse sobre una lista local.
    """

    download_requested = pyqtSignal(dict, str)   # vídeo, código de calidad

    def __init__(self, video: dict, badge: str = "") -> None:
        super().__init__()
        self.video = video
        self.setObjectName("Card")
        self.setFixedSize(258, 268)
        self._base_geometry: Optional[QRect] = None
        self._hover_anim: Optional[QPropertyAnimation] = None
        self._build_ui(badge)

    def _build_ui(self, badge: str) -> None:
        """Construye la disposición visual de la tarjeta."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        # --- Miniatura (se rellenará de forma asíncrona) ---
        self._thumb = QLabel("◼ cargando…")
        self._thumb.setFixedSize(242, 136)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            "background:#04101E;border:1px solid #1A3A5C;"
            "color:#3C5A74;font-family:'Courier New';"
        )
        layout.addWidget(self._thumb)

        if badge:
            badge_label = QLabel(badge, self._thumb)
            is_hd = badge.upper() in ("HD", "FHD", "QHD", "4K", "1080P", "4320P")
            badge_label.setObjectName("BadgeHD" if is_hd else "Badge")
            badge_label.move(8, 8)
            badge_label.adjustSize()

        # --- Título ---
        title = QLabel(self.video.get("title", ""))
        title.setWordWrap(True)
        title.setStyleSheet("font-weight:bold;color:#C8E8FF;")
        title.setFixedHeight(34)
        layout.addWidget(title)

        # --- Canal ---
        channel = QLabel(self.video.get("channel", "Desconocido"))
        channel.setObjectName("Muted")
        layout.addWidget(channel)

        # --- Duración y vistas en estilo LCD ---
        meta = QHBoxLayout()
        duration = QLabel(self.video.get("duration_text", "--:--"))
        duration.setStyleSheet("font-family:'Courier New';color:#33CCFF;")
        views = QLabel(_format_views(int(self.video.get("view_count", 0))))
        views.setStyleSheet("font-family:'Courier New';color:#6A9EC0;")
        meta.addWidget(duration)
        meta.addStretch(1)
        meta.addWidget(views)
        layout.addLayout(meta)

        # --- Controles de descarga ---
        controls = QHBoxLayout()
        self._quality = QComboBox()
        for code, label in _QUALITY_LABELS:
            self._quality.addItem(label, code)
        self._quality.setCurrentIndex(5)  # 1080p por defecto.
        controls.addWidget(self._quality, 1)

        download = QPushButton("▼")
        download.setFixedWidth(40)
        download.setToolTip("Añadir a la cola de descargas")
        download.clicked.connect(self._emit_download)
        controls.addWidget(download)
        layout.addLayout(controls)

    def _emit_download(self) -> None:
        """Emite la solicitud de descarga con la calidad seleccionada."""
        code = self._quality.currentData()
        self.download_requested.emit(self.video, code)

    def set_thumbnail(self, path: str) -> None:
        """Asigna la miniatura descargada a la tarjeta."""
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            self._thumb.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumb.setPixmap(scaled)

    # ----- Efecto de hover: escala 1.03x -------------------------------
    def enterEvent(self, event) -> None:  # noqa: N802 - API de Qt.
        """Agranda ligeramente la tarjeta al pasar el ratón."""
        if self._base_geometry is None:
            self._base_geometry = self.geometry()
        self.raise_()
        target = QRect(self._base_geometry)
        # Crecimiento del 3 % manteniendo el centro de la tarjeta.
        target.adjust(-4, -4, 4, 4)
        self._animate_geometry(target)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - API de Qt.
        """Restaura el tamaño original al salir el ratón."""
        if self._base_geometry is not None:
            self._animate_geometry(self._base_geometry)
        super().leaveEvent(event)

    def _animate_geometry(self, target: QRect) -> None:
        """Anima el cambio de geometría de la tarjeta."""
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(140)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim = anim
        anim.start()

    # ----- Soporte de arrastre hacia las listas ------------------------
    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - API de Qt.
        """Inicia un arrastre con los datos del vídeo serializados."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(VIDEO_MIME, json.dumps(self.video).encode("utf-8"))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class SearchScreen(QWidget):
    """Pantalla del buscador: barra retro + rejilla de resultados."""

    download_requested = pyqtSignal(dict, str)
    status_message = pyqtSignal(str)

    def __init__(self, thumbnail_manager, settings_manager) -> None:
        super().__init__()
        self._thumbnails = thumbnail_manager
        self._settings = settings_manager
        self._cards: dict[str, VideoCard] = {}
        self._build_ui()
        self._thumbnails.thumbnail_ready.connect(self._apply_thumbnail)

    def _build_ui(self) -> None:
        """Construye la disposición de la pantalla de búsqueda."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("BUSCADOR")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        bar = QHBoxLayout()
        self._search_bar = QLineEdit()
        self._search_bar.setObjectName("SearchBar")
        self._search_bar.setPlaceholderText(
            "Escribe tu búsqueda y pulsa Intro…"
        )
        self._search_bar.returnPressed.connect(self._do_search)
        bar.addWidget(self._search_bar, 1)
        button = QPushButton("Buscar")
        button.clicked.connect(self._do_search)
        bar.addWidget(button)
        layout.addLayout(bar)

        self._info = QLabel("Introduce un término para buscar en YouTube.")
        self._info.setObjectName("Muted")
        layout.addWidget(self._info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(14)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._grid_host)
        layout.addWidget(scroll, 1)

    def _do_search(self) -> None:
        """Lanza una búsqueda asíncrona con el texto introducido."""
        query = self._search_bar.text().strip()
        if not query:
            return
        self._info.setText(f"Buscando «{query}»…")
        # La búsqueda es pública: nunca usa cookies del navegador.
        task = SearchTask(
            "query",
            query=query,
            limit=20,
            browser=None,
            proxy=self._settings.get("proxy") or None,
        )
        task.signals.results.connect(self._show_results)
        task.signals.error.connect(self._show_error)
        QThreadPool.globalInstance().start(task)

    def _clear_grid(self) -> None:
        """Elimina todas las tarjetas de la rejilla."""
        self._cards.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_results(self, _mode: str, videos: list) -> None:
        """Rellena la rejilla con las tarjetas de los vídeos encontrados."""
        self._clear_grid()
        if not videos:
            self._info.setText("Sin resultados para esa búsqueda.")
            return
        self._info.setText(f"{len(videos)} resultados.")
        for index, video in enumerate(videos):
            card = VideoCard(video)
            card.download_requested.connect(self.download_requested)
            self._cards[video["id"]] = card
            self._grid.addWidget(card, index // 3, index % 3)
            self._thumbnails.request(video["id"], video["thumbnail"])
        fade_in(self._grid_host, 400)

    def _show_error(self, _mode: str, message: str) -> None:
        """Muestra un mensaje de error de búsqueda."""
        self._info.setText(f"Error: {message}")
        self.status_message.emit(f"Búsqueda fallida: {message}")

    def _apply_thumbnail(self, video_id: str, path: str) -> None:
        """Asigna una miniatura recién descargada a su tarjeta."""
        card = self._cards.get(video_id)
        if card is not None:
            card.set_thumbnail(path)


if __name__ == "__main__":
    import sys

    from app.ui.settings import SettingsManager
    from app.utils.thumbnails import ThumbnailManager

    app = QApplication(sys.argv)
    screen = SearchScreen(ThumbnailManager(), SettingsManager())
    screen.resize(900, 620)
    screen.show()
    sys.exit(app.exec())
