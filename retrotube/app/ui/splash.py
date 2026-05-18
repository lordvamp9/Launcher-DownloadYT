"""Pantalla de arranque (splash) con estética Windows Media Player.

Efectos:
- Aparición del logo con línea de barrido horizontal ("scan line").
- Barra de progreso estilo LED que se llena de izquierda a derecha.
- Al terminar (~2,5 s) emite :data:`SplashScreen.finished`.
"""
from __future__ import annotations

from PyQt6.QtCore import QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QProgressBar, QWidget

from app import __version__

# Duración total de la animación de arranque, en milisegundos.
_TOTAL_MS = 2500
_TICK_MS = 25


class SplashScreen(QWidget):
    """Ventana sin marco que presenta la animación de inicio."""

    finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(560, 320)
        self._elapsed = 0
        self._scan_y = 0.0

        # Barra de progreso LED en la parte inferior.
        self._bar = QProgressBar(self)
        self._bar.setObjectName("LedBar")
        self._bar.setGeometry(60, 250, 440, 12)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._center_on_screen()

    def _center_on_screen(self) -> None:
        """Centra la ventana en la pantalla principal."""
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )

    def start(self) -> None:
        """Inicia la animación de arranque."""
        self._elapsed = 0
        self._timer.start(_TICK_MS)

    def _tick(self) -> None:
        """Avanza el progreso y la línea de barrido en cada pulso del timer."""
        self._elapsed += _TICK_MS
        ratio = min(1.0, self._elapsed / _TOTAL_MS)
        self._bar.setValue(int(ratio * 100))
        # La línea de barrido recorre el área del logo de forma cíclica.
        self._scan_y = (self._scan_y + 6) % 170
        self.update()
        if self._elapsed >= _TOTAL_MS:
            self._timer.stop()
            self.finished.emit()

    def paintEvent(self, event) -> None:  # noqa: N802 - API de Qt.
        """Dibuja el fondo biselado, el logo y el efecto scanline."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fondo degradado azul-negro profundo.
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor("#0A1626"))
        gradient.setColorAt(1.0, QColor("#04080F"))
        painter.fillRect(self.rect(), gradient)

        # Borde biselado con brillo cian.
        painter.setPen(QPen(QColor("#00AAFF"), 2))
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
        painter.setPen(QPen(QColor("#1A3A5C"), 1))
        painter.drawRect(self.rect().adjusted(4, 4, -5, -5))

        # Logo principal con tipografía de impacto.
        logo_area = QRect(0, 60, self.width(), 110)
        painter.setFont(QFont("Segoe UI", 34, QFont.Weight.Black))
        painter.setPen(QColor("#00AAFF"))
        painter.drawText(
            logo_area, Qt.AlignmentFlag.AlignCenter, "RetroTube"
        )
        painter.setFont(QFont("Courier New", 12))
        painter.setPen(QColor("#6A9EC0"))
        painter.drawText(
            QRect(0, 150, self.width(), 30),
            Qt.AlignmentFlag.AlignCenter,
            f"D O W N L O A D E R   ·   v{__version__}",
        )

        # Efecto "scan line": franja cian semitransparente que recorre el logo.
        scan_rect = QRect(40, 55 + int(self._scan_y), self.width() - 80, 3)
        painter.fillRect(scan_rect, QColor(51, 204, 255, 120))
        glow = QRect(40, 55 + int(self._scan_y) - 8, self.width() - 80, 18)
        painter.fillRect(glow, QColor(0, 170, 255, 28))

        # Etiqueta de estado sobre la barra de progreso.
        painter.setFont(QFont("Courier New", 9))
        painter.setPen(QColor("#33CCFF"))
        painter.drawText(
            QRect(60, 228, 440, 18),
            Qt.AlignmentFlag.AlignLeft,
            "CARGANDO MÓDULOS…",
        )
        painter.end()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    splash = SplashScreen()
    splash.finished.connect(app.quit)
    splash.show()
    splash.start()
    sys.exit(app.exec())
