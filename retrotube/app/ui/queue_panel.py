"""Panel de cola de descargas en tiempo real.

Cada ítem muestra progreso individual, velocidad, ETA y un botón de cancelar.
Al añadirse un ítem el panel produce un destello azul y la tarjeta entra
deslizándose desde abajo.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.utils.animations import flash, pulse, slide_in_from_bottom


class QueueItem(QFrame):
    """Tarjeta individual de un vídeo dentro de la cola de descargas."""

    cancel_requested = pyqtSignal(str)

    def __init__(self, task_id: str, title: str, channel: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.setObjectName("Card")
        self._build_ui(title, channel)

    def _build_ui(self, title: str, channel: str) -> None:
        """Construye la disposición de la tarjeta de cola."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self._dot = QLabel("●")
        self._dot.setStyleSheet("color:#33CCFF;font-size:14px;")
        header.addWidget(self._dot)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight:bold;color:#C8E8FF;")
        title_label.setWordWrap(True)
        header.addWidget(title_label, 1)

        self._cancel = QPushButton("✕")
        self._cancel.setObjectName("DangerButton")
        self._cancel.setFixedSize(26, 26)
        self._cancel.clicked.connect(
            lambda: self.cancel_requested.emit(self.task_id)
        )
        header.addWidget(self._cancel)
        layout.addLayout(header)

        channel_label = QLabel(channel)
        channel_label.setObjectName("Muted")
        layout.addWidget(channel_label)

        self._bar = QProgressBar()
        self._bar.setObjectName("LedBar")
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        layout.addWidget(self._bar)

        stats = QHBoxLayout()
        self._speed = QLabel("-- KiB/s")
        self._speed.setProperty("class", "lcd")
        self._speed.setStyleSheet("font-family:'Courier New';color:#33CCFF;")
        self._eta = QLabel("ETA --:--")
        self._eta.setStyleSheet("font-family:'Courier New';color:#6A9EC0;")
        self._status = QLabel("En cola")
        self._status.setStyleSheet("font-family:'Courier New';color:#6A9EC0;")
        stats.addWidget(self._speed)
        stats.addStretch(1)
        stats.addWidget(self._eta)
        stats.addStretch(1)
        stats.addWidget(self._status)
        layout.addLayout(stats)

        # Pulso del indicador mientras la descarga está activa.
        self._pulse = pulse(self._dot, 800)

    def set_progress(self, percent: float, speed: str, eta: str) -> None:
        """Actualiza la barra y los indicadores LCD de la tarjeta."""
        self._bar.setValue(int(percent))
        self._speed.setText(speed)
        self._eta.setText(f"ETA {eta}")
        self._status.setText("Descargando")
        self._status.setStyleSheet(
            "font-family:'Courier New';color:#33CCFF;"
        )

    def set_finished(self) -> None:
        """Marca la tarjeta como completada."""
        self._bar.setValue(100)
        self._status.setText("Completado")
        self._status.setStyleSheet(
            "font-family:'Courier New';color:#33FF88;"
        )
        self._dot.setStyleSheet("color:#33FF88;font-size:14px;")
        self._pulse.stop()
        self._dot.setGraphicsEffect(None)
        self._cancel.setEnabled(False)

    def set_failed(self, message: str) -> None:
        """Marca la tarjeta como fallida o cancelada."""
        self._status.setText(message[:40])
        self._status.setStyleSheet(
            "font-family:'Courier New';color:#FF5577;"
        )
        self._dot.setStyleSheet("color:#FF5577;font-size:14px;")
        self._pulse.stop()
        self._dot.setGraphicsEffect(None)
        self._cancel.setEnabled(False)


class QueuePanel(QWidget):
    """Contenedor desplazable de la cola de descargas."""

    cancel_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._items: dict[str, QueueItem] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Construye el panel con cabecera y zona desplazable."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("COLA DE DESCARGAS")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self._empty = QLabel("Sin descargas activas.")
        self._empty.setObjectName("Muted")
        layout.addWidget(self._empty)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._container = QWidget()
        self._list = QVBoxLayout(self._container)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(8)
        self._list.addStretch(1)
        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

    def add_item(self, task_id: str, title: str, channel: str) -> None:
        """Añade un vídeo a la cola con destello y deslizamiento."""
        if task_id in self._items:
            return
        self._empty.setVisible(False)
        item = QueueItem(task_id, title, channel)
        item.cancel_requested.connect(self.cancel_requested)
        # Se inserta antes del stretch final para conservar el orden.
        self._list.insertWidget(self._list.count() - 1, item)
        self._items[task_id] = item
        # Animaciones retro: deslizamiento del ítem y destello del panel.
        slide_in_from_bottom(item)
        flash(self)

    def update_progress(
        self, task_id: str, percent: float, speed: str, eta: str
    ) -> None:
        """Refleja el progreso de una descarga concreta."""
        item = self._items.get(task_id)
        if item is not None:
            item.set_progress(percent, speed, eta)

    def mark_finished(self, task_id: str) -> None:
        """Marca una descarga como completada."""
        item = self._items.get(task_id)
        if item is not None:
            item.set_finished()

    def mark_failed(self, task_id: str, message: str) -> None:
        """Marca una descarga como fallida o cancelada."""
        item = self._items.get(task_id)
        if item is not None:
            item.set_failed(message)


if __name__ == "__main__":
    import sys

    from PyQt6.QtCore import QTimer

    app = QApplication(sys.argv)
    panel = QueuePanel()
    panel.setObjectName("Panel")
    panel.resize(320, 480)
    panel.show()
    panel.add_item("demo1", "Vídeo de demostración retro", "Canal Retro")
    QTimer.singleShot(
        600, lambda: panel.update_progress("demo1", 45.0, "1.2 MiB/s", "00:18")
    )
    QTimer.singleShot(1400, lambda: panel.mark_finished("demo1"))
    sys.exit(app.exec())
