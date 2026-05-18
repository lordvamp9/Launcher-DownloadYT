"""Pantalla "Mis descargas": biblioteca local de vídeos descargados.

Permite filtrar por canal, ordenar, abrir la carpeta contenedora,
reproducir el archivo y eliminar registros (con o sin el archivo en disco).
"""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QUrl

from app.core.database import Database


def _human_size(num_bytes: int) -> str:
    """Convierte bytes a una cadena legible (KB/MB/GB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


class DownloadedCard(QFrame):
    """Tarjeta de un vídeo ya descargado, con acciones de gestión."""

    action_requested = pyqtSignal(str, str)   # acción, video_id

    def __init__(self, record: dict) -> None:
        super().__init__()
        self.record = record
        self.setObjectName("Card")
        self.setFixedSize(258, 300)
        self._build_ui()

    def _build_ui(self) -> None:
        """Construye la tarjeta con miniatura, datos y botones."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        thumb = QLabel()
        thumb.setFixedSize(242, 136)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            "background:#04101E;border:1px solid #1A3A5C;"
            "color:#3C5A74;font-family:'Courier New';"
        )
        pixmap = QPixmap(self.record.get("thumbnail_path", ""))
        if not pixmap.isNull():
            thumb.setPixmap(pixmap.scaled(
                thumb.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            ))
        else:
            thumb.setText("◼ sin miniatura")
        layout.addWidget(thumb)

        title = QLabel(self.record.get("title", ""))
        title.setWordWrap(True)
        title.setFixedHeight(34)
        title.setStyleSheet("font-weight:bold;color:#C8E8FF;")
        layout.addWidget(title)

        channel = QLabel(self.record.get("channel", "Desconocido"))
        channel.setObjectName("Muted")
        layout.addWidget(channel)

        size = QLabel(_human_size(int(self.record.get("size_bytes", 0))))
        size.setStyleSheet("font-family:'Courier New';color:#33CCFF;")
        layout.addWidget(size)

        # Fila superior de acciones.
        row1 = QHBoxLayout()
        play = QPushButton("▶ Reproducir")
        play.clicked.connect(lambda: self._emit("play"))
        folder = QPushButton("📁")
        folder.setFixedWidth(40)
        folder.setObjectName("GhostButton")
        folder.setToolTip("Abrir carpeta")
        folder.clicked.connect(lambda: self._emit("folder"))
        row1.addWidget(play, 1)
        row1.addWidget(folder)
        layout.addLayout(row1)

        # Fila inferior de eliminación.
        row2 = QHBoxLayout()
        del_record = QPushButton("Quitar registro")
        del_record.setObjectName("GhostButton")
        del_record.clicked.connect(lambda: self._emit("delete_record"))
        del_all = QPushButton("Borrar todo")
        del_all.setObjectName("DangerButton")
        del_all.clicked.connect(lambda: self._emit("delete_all"))
        row2.addWidget(del_record, 1)
        row2.addWidget(del_all, 1)
        layout.addLayout(row2)

    def _emit(self, action: str) -> None:
        """Emite una solicitud de acción para esta tarjeta."""
        self.action_requested.emit(action, self.record["id"])


class DownloadsScreen(QWidget):
    """Biblioteca de vídeos descargados con filtros y estadísticas."""

    status_message = pyqtSignal(str)

    def __init__(self, database: Database) -> None:
        super().__init__()
        self._db = database
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Construye la disposición de la pantalla."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        title = QLabel("MIS DESCARGAS")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        # Panel de estadísticas.
        self._stats = QLabel()
        self._stats.setObjectName("Muted")
        self._stats.setStyleSheet(
            "font-family:'Courier New';color:#33CCFF;font-size:13px;"
        )
        layout.addWidget(self._stats)

        # Controles de filtro.
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Canal:"))
        self._channel_filter = QComboBox()
        self._channel_filter.currentIndexChanged.connect(self._render)
        filters.addWidget(self._channel_filter, 1)
        filters.addWidget(QLabel("Ordenar:"))
        self._order = QComboBox()
        self._order.addItems(["fecha", "canal", "tamaño"])
        self._order.currentIndexChanged.connect(self._render)
        filters.addWidget(self._order, 1)
        reload_btn = QPushButton("↻")
        reload_btn.setObjectName("GhostButton")
        reload_btn.setFixedWidth(40)
        reload_btn.clicked.connect(self.refresh)
        filters.addWidget(reload_btn)
        layout.addLayout(filters)

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
        """Recarga las estadísticas, los filtros y la rejilla desde la BD."""
        stats = self._db.stats()
        self._stats.setText(
            f"  {stats['total_videos']} vídeos   ·   "
            f"{stats['total_gb']} GB   ·   "
            f"{stats['unique_channels']} canales"
        )
        # Reconstruye el filtro de canales conservando la selección.
        current = self._channel_filter.currentText()
        channels = sorted({
            d["channel"] for d in self._db.list_downloads() if d["channel"]
        })
        self._channel_filter.blockSignals(True)
        self._channel_filter.clear()
        self._channel_filter.addItem("Todos")
        self._channel_filter.addItems(channels)
        if current in channels:
            self._channel_filter.setCurrentText(current)
        self._channel_filter.blockSignals(False)
        self._render()

    def _render(self) -> None:
        """Dibuja las tarjetas según los filtros activos."""
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        channel = self._channel_filter.currentText()
        records = self._db.list_downloads(
            channel=None if channel in ("", "Todos") else channel,
            order_by=self._order.currentText(),
        )
        if not records:
            empty = QLabel("Aún no has descargado ningún vídeo.")
            empty.setObjectName("Muted")
            self._grid.addWidget(empty, 0, 0)
            return
        for index, record in enumerate(records):
            card = DownloadedCard(record)
            card.action_requested.connect(self._handle_action)
            self._grid.addWidget(card, index // 3, index % 3)

    def _handle_action(self, action: str, video_id: str) -> None:
        """Atiende las acciones solicitadas por una tarjeta."""
        record = self._db.get_download(video_id)
        if record is None:
            return
        path = Path(record.get("local_path", ""))

        if action == "play":
            if path.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            else:
                self.status_message.emit("El archivo ya no existe en disco.")
        elif action == "folder":
            folder = path.parent if path.parent.exists() else Path.home()
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        elif action == "delete_record":
            self._db.delete_download(video_id)
            self.status_message.emit("Registro eliminado.")
            self.refresh()
        elif action == "delete_all":
            confirm = QMessageBox.question(
                self, "Confirmar borrado",
                "¿Eliminar el archivo del disco y su registro?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            try:
                if path.is_file():
                    os.unlink(path)
            except OSError as exc:
                self.status_message.emit(f"No se pudo borrar el archivo: {exc}")
            self._db.delete_download(video_id)
            self.status_message.emit("Archivo y registro eliminados.")
            self.refresh()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    screen = DownloadsScreen(Database())
    screen.resize(900, 640)
    screen.show()
    sys.exit(app.exec())
