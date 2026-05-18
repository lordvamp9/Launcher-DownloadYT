"""Pantalla "Mis listas": listas de reproducción locales.

Funciones:
- Crear listas con nombre y color personalizado.
- Arrastrar y soltar vídeos desde el buscador/feed hacia una lista.
- Descargar una lista de YouTube completa por URL (errores por ítem).
- Exportar una lista local a formato M3U.
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.database import Database
from app.core.search import SearchTask
from app.core.validators import InvalidYouTubeURL, validate_playlist_url
from app.ui.search import VIDEO_MIME


class PlaylistList(QListWidget):
    """Lista de playlists que acepta vídeos soltados mediante arrastre."""

    video_dropped = pyqtSignal(int, dict)   # playlist_id, vídeo

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - API de Qt.
        """Acepta el arrastre solo si transporta un vídeo de RetroTube."""
        if event.mimeData().hasFormat(VIDEO_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - API de Qt.
        """Permite mover el arrastre sobre los elementos de la lista."""
        if event.mimeData().hasFormat(VIDEO_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 - API de Qt.
        """Asocia el vídeo soltado a la playlist situada bajo el cursor."""
        item = self.itemAt(event.position().toPoint())
        if item is None:
            event.ignore()
            return
        try:
            raw = bytes(event.mimeData().data(VIDEO_MIME)).decode("utf-8")
            video = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            event.ignore()
            return
        playlist_id = item.data(Qt.ItemDataRole.UserRole)
        self.video_dropped.emit(int(playlist_id), video)
        event.acceptProposedAction()


class PlaylistsScreen(QWidget):
    """Gestión de listas de reproducción locales."""

    download_requested = pyqtSignal(dict, str)
    status_message = pyqtSignal(str)

    def __init__(self, database: Database, settings_manager) -> None:
        super().__init__()
        self._db = database
        self._settings = settings_manager
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Construye la disposición de dos columnas."""
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(12)

        title = QLabel("MIS LISTAS")
        title.setObjectName("ScreenTitle")
        root.addWidget(title)

        hint = QLabel("Arrastra vídeos del buscador hasta una lista.")
        hint.setObjectName("Muted")
        root.addWidget(hint)

        columns = QHBoxLayout()
        columns.setSpacing(14)

        # --- Columna izquierda: listas ---
        left = QVBoxLayout()
        self._playlists = PlaylistList()
        self._playlists.video_dropped.connect(self._on_video_dropped)
        self._playlists.currentItemChanged.connect(self._show_items)
        left.addWidget(self._playlists, 1)
        new_btn = QPushButton("+ Nueva lista")
        new_btn.clicked.connect(self._create_playlist)
        del_btn = QPushButton("Eliminar lista")
        del_btn.setObjectName("DangerButton")
        del_btn.clicked.connect(self._delete_playlist)
        left.addWidget(new_btn)
        left.addWidget(del_btn)
        columns.addLayout(left, 1)

        # --- Columna derecha: contenido de la lista ---
        right = QVBoxLayout()
        self._items = QListWidget()
        right.addWidget(self._items, 1)
        remove_item = QPushButton("Quitar vídeo seleccionado")
        remove_item.setObjectName("GhostButton")
        remove_item.clicked.connect(self._remove_item)
        export_btn = QPushButton("Exportar como M3U")
        export_btn.clicked.connect(self._export_m3u)
        right.addWidget(remove_item)
        right.addWidget(export_btn)
        columns.addLayout(right, 2)
        root.addLayout(columns, 1)

        # --- Descarga de una lista de YouTube por URL ---
        url_row = QHBoxLayout()
        self._url = QLineEdit()
        self._url.setPlaceholderText(
            "Pega la URL de una lista de YouTube para descargarla…"
        )
        download_pl = QPushButton("Descargar lista de YouTube")
        download_pl.clicked.connect(self._download_youtube_playlist)
        url_row.addWidget(self._url, 1)
        url_row.addWidget(download_pl)
        root.addLayout(url_row)

    # ----- Listas locales ----------------------------------------------
    def refresh(self) -> None:
        """Recarga la columna de listas desde la base de datos."""
        self._playlists.clear()
        for playlist in self._db.list_playlists():
            item = QListWidgetItem(
                f"●  {playlist['name']}  ({playlist['count']})"
            )
            item.setData(Qt.ItemDataRole.UserRole, playlist["id"])
            item.setForeground(Qt.GlobalColor.white)
            # El bullet adopta el color personalizado de la lista.
            item.setData(Qt.ItemDataRole.DecorationRole, None)
            self._playlists.addItem(item)
        self._items.clear()

    def _current_playlist_id(self) -> int | None:
        """Devuelve el ID de la lista seleccionada, o ``None``."""
        item = self._playlists.currentItem()
        if item is None:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def _create_playlist(self) -> None:
        """Pide nombre y color y crea una nueva lista local."""
        name, ok = QInputDialog.getText(
            self, "Nueva lista", "Nombre de la lista:"
        )
        if not ok or not name.strip():
            return
        color = QColorDialog.getColor()
        hex_color = color.name() if color.isValid() else "#00AAFF"
        self._db.create_playlist(name.strip(), hex_color)
        self.status_message.emit(f"Lista «{name.strip()}» creada.")
        self.refresh()

    def _delete_playlist(self) -> None:
        """Elimina la lista seleccionada."""
        playlist_id = self._current_playlist_id()
        if playlist_id is None:
            return
        self._db.delete_playlist(playlist_id)
        self.status_message.emit("Lista eliminada.")
        self.refresh()

    def _show_items(self) -> None:
        """Muestra los vídeos de la lista seleccionada."""
        self._items.clear()
        playlist_id = self._current_playlist_id()
        if playlist_id is None:
            return
        for entry in self._db.playlist_items(playlist_id):
            label = f"{entry['title']}  —  {entry['channel']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            self._items.addItem(item)

    def _remove_item(self) -> None:
        """Quita el vídeo seleccionado de la lista actual."""
        item = self._items.currentItem()
        if item is None:
            return
        self._db.remove_playlist_item(int(item.data(Qt.ItemDataRole.UserRole)))
        self.status_message.emit("Vídeo quitado de la lista.")
        self.refresh()

    def _on_video_dropped(self, playlist_id: int, video: dict) -> None:
        """Añade a la lista un vídeo soltado mediante arrastre."""
        added = self._db.add_to_playlist(playlist_id, video)
        if added:
            self.status_message.emit("Vídeo añadido a la lista.")
        else:
            self.status_message.emit("Ese vídeo ya estaba en la lista.")
        self.refresh()

    # ----- Integración con YouTube -------------------------------------
    def _download_youtube_playlist(self) -> None:
        """Descarga todos los vídeos de una lista de YouTube por URL."""
        url = self._url.text().strip()
        try:
            validate_playlist_url(url)
        except InvalidYouTubeURL as exc:
            self.status_message.emit(f"URL de lista inválida: {exc}")
            return
        self.status_message.emit("Obteniendo vídeos de la lista…")
        # Las listas públicas se extraen sin cookies del navegador.
        task = SearchTask(
            "playlist",
            query=url,
            limit=40,
            browser=None,
            proxy=self._settings.get("proxy") or None,
        )
        task.signals.results.connect(self._enqueue_playlist)
        task.signals.error.connect(
            lambda _m, err: self.status_message.emit(f"Error de lista: {err}")
        )
        QThreadPool.globalInstance().start(task)

    def _enqueue_playlist(self, _mode: str, videos: list) -> None:
        """Encola la descarga de cada vídeo de la lista de forma individual."""
        if not videos:
            self.status_message.emit("La lista no contenía vídeos.")
            return
        quality = self._settings.get("default_quality")
        for video in videos:
            # La gestión de errores es por ítem: cada tarea falla por separado.
            self.download_requested.emit(video, quality)
        self.status_message.emit(
            f"{len(videos)} vídeos de la lista añadidos a la cola."
        )

    def _export_m3u(self) -> None:
        """Exporta la lista seleccionada a un archivo M3U."""
        playlist_id = self._current_playlist_id()
        if playlist_id is None:
            self.status_message.emit("Selecciona primero una lista.")
            return
        entries = self._db.playlist_items(playlist_id)
        if not entries:
            self.status_message.emit("La lista está vacía.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar M3U", str(Path.home() / "lista.m3u"),
            "Listas M3U (*.m3u)"
        )
        if not path:
            return
        lines = ["#EXTM3U"]
        for entry in entries:
            lines.append(f"#EXTINF:{entry['duration']},{entry['title']}")
            lines.append(entry["url"])
        try:
            Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            self.status_message.emit(f"No se pudo exportar: {exc}")
            return
        self.status_message.emit(f"Lista exportada a {path}")


if __name__ == "__main__":
    import sys

    from app.ui.settings import SettingsManager

    app = QApplication(sys.argv)
    screen = PlaylistsScreen(Database(), SettingsManager())
    screen.resize(880, 620)
    screen.show()
    sys.exit(app.exec())
