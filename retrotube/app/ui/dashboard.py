"""Pantalla de dashboard: feed de recomendaciones o tendencias.

Si hay sesión activa se solicita el feed personalizado del usuario; en caso
contrario se muestran las tendencias públicas de YouTube. Las miniaturas se
descargan de forma asíncrona.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.search import SearchTask
from app.ui.search import VideoCard
from app.utils.animations import fade_in


class DashboardScreen(QWidget):
    """Feed central de recomendaciones del dashboard."""

    download_requested = pyqtSignal(dict, str)
    status_message = pyqtSignal(str)

    def __init__(
        self, thumbnail_manager, settings_manager, auth_manager
    ) -> None:
        super().__init__()
        self._thumbnails = thumbnail_manager
        self._settings = settings_manager
        self._auth = auth_manager
        self._cards: dict[str, VideoCard] = {}
        self._build_ui()
        self._thumbnails.thumbnail_ready.connect(self._apply_thumbnail)

    def _build_ui(self) -> None:
        """Construye la disposición del feed."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("RECOMENDACIONES")
        title.setObjectName("ScreenTitle")
        header.addWidget(title)
        header.addStretch(1)
        refresh = QPushButton("↻ Actualizar")
        refresh.setObjectName("GhostButton")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        layout.addLayout(header)

        self._info = QLabel("Cargando feed…")
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

    def refresh(self) -> None:
        """Recarga el feed según el estado de sesión actual."""
        authenticated = self._auth.authenticated
        mode = "recommended" if authenticated else "trending"
        origin = "tu feed personal" if authenticated else "tendencias públicas"
        self._info.setText(f"Cargando {origin}…")
        task = SearchTask(
            mode,
            limit=21,
            browser=self._settings.get("browser") if authenticated else None,
            proxy=self._settings.get("proxy") or None,
        )
        task.signals.results.connect(self._show_results)
        task.signals.error.connect(self._show_error)
        QThreadPool.globalInstance().start(task)

    def _clear_grid(self) -> None:
        """Elimina todas las tarjetas del feed."""
        self._cards.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_results(self, mode: str, videos: list) -> None:
        """Rellena el feed con las tarjetas recibidas."""
        self._clear_grid()
        if not videos:
            self._info.setText("No se pudo cargar el feed en este momento.")
            return
        origin = "Feed personal" if mode == "recommended" else "Tendencias"
        self._info.setText(f"{origin} · {len(videos)} vídeos.")
        for index, video in enumerate(videos):
            card = VideoCard(video, badge="HD")
            card.download_requested.connect(self.download_requested)
            self._cards[video["id"]] = card
            self._grid.addWidget(card, index // 3, index % 3)
            self._thumbnails.request(video["id"], video["thumbnail"])
        fade_in(self._grid_host, 450)

    def _show_error(self, _mode: str, message: str) -> None:
        """Muestra un error de carga del feed."""
        self._info.setText(f"Error al cargar el feed: {message}")
        self.status_message.emit(f"Feed no disponible: {message}")

    def _apply_thumbnail(self, video_id: str, path: str) -> None:
        """Asigna una miniatura descargada a su tarjeta del feed."""
        card = self._cards.get(video_id)
        if card is not None:
            card.set_thumbnail(path)


if __name__ == "__main__":
    import sys

    from app.core.auth import AuthManager
    from app.ui.settings import SettingsManager
    from app.utils.thumbnails import ThumbnailManager

    app = QApplication(sys.argv)
    screen = DashboardScreen(
        ThumbnailManager(), SettingsManager(), AuthManager()
    )
    screen.resize(900, 620)
    screen.show()
    screen.refresh()
    sys.exit(app.exec())
