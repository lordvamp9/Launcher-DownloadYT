"""Animaciones reutilizables con ``QPropertyAnimation``.

Estética inspirada en Windows Media Player (años 2000): transiciones
exageradas, deslizamientos y pulsos luminosos. Cada función conserva una
referencia a la animación dentro del propio widget para evitar que el
recolector de basura la destruya antes de terminar.
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QObject,
    QPoint,
    QPropertyAnimation,
    QSequentialAnimationGroup,
)
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QWidget


def _store(widget: QObject, name: str, animation: QObject) -> None:
    """Guarda la animación como atributo para evitar su recolección."""
    setattr(widget, f"_anim_{name}", animation)


def fade_in(widget: QWidget, duration: int = 350) -> QPropertyAnimation:
    """Aplica un efecto de aparición gradual (opacidad 0 -> 1)."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity")
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    _store(widget, "fade", animation)
    animation.start()
    return animation


def slide_in_from_bottom(
    widget: QWidget,
    distance: int = 48,
    duration: int = 420,
) -> QPropertyAnimation:
    """Desliza el widget desde abajo hacia su posición final."""
    end_pos = widget.pos()
    start_pos = QPoint(end_pos.x(), end_pos.y() + distance)
    widget.move(start_pos)
    animation = QPropertyAnimation(widget, b"pos")
    animation.setDuration(duration)
    animation.setStartValue(start_pos)
    animation.setEndValue(end_pos)
    animation.setEasingCurve(QEasingCurve.Type.OutBack)
    _store(widget, "slide", animation)
    animation.start()
    return animation


def slide_up_out(
    widget: QWidget,
    distance: int = 60,
    duration: int = 420,
) -> QPropertyAnimation:
    """Desliza el widget hacia arriba (usado para salir del splash)."""
    start_pos = widget.pos()
    end_pos = QPoint(start_pos.x(), start_pos.y() - distance)
    animation = QPropertyAnimation(widget, b"pos")
    animation.setDuration(duration)
    animation.setStartValue(start_pos)
    animation.setEndValue(end_pos)
    animation.setEasingCurve(QEasingCurve.Type.InCubic)
    _store(widget, "slideout", animation)
    animation.start()
    return animation


def pulse(widget: QWidget, period: int = 800) -> QPropertyAnimation:
    """Crea un pulso de opacidad en bucle (1.0 -> 0.4 -> 1.0).

    Se usa, por ejemplo, en el icono de descarga activa.
    """
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity")
    animation.setDuration(period)
    animation.setStartValue(1.0)
    animation.setKeyValueAt(0.5, 0.4)
    animation.setEndValue(1.0)
    animation.setLoopCount(-1)  # Bucle infinito.
    animation.setEasingCurve(QEasingCurve.Type.InOutSine)
    _store(widget, "pulse", animation)
    animation.start()
    return animation


def flash(widget: QWidget, duration: int = 500) -> QSequentialAnimationGroup:
    """Destello breve de opacidad usado al añadir ítems a la cola."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    group = QSequentialAnimationGroup(widget)

    up = QPropertyAnimation(effect, b"opacity")
    up.setDuration(duration // 2)
    up.setStartValue(1.0)
    up.setEndValue(0.25)
    down = QPropertyAnimation(effect, b"opacity")
    down.setDuration(duration // 2)
    down.setStartValue(0.25)
    down.setEndValue(1.0)

    group.addAnimation(up)
    group.addAnimation(down)
    _store(widget, "flash", group)
    group.start()
    return group


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication, QLabel

    app = QApplication(sys.argv)
    label = QLabel("RetroTube · demo de animaciones")
    label.setStyleSheet("background:#080C14;color:#00AAFF;padding:60px;"
                        "font-size:20px;")
    label.resize(420, 160)
    label.show()
    fade_in(label, 900)
    pulse(label, 1200)
    sys.exit(app.exec())
