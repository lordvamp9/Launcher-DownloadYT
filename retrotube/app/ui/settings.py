"""Pantalla de configuración y gestor de ajustes persistentes.

El archivo ``settings.json`` se guarda en el directorio de datos de la app
con permisos restrictivos (600). NUNCA contiene credenciales: solo
preferencias de descarga, navegador para cookies y proxy opcional.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.auth import SUPPORTED_BROWSERS
from app.core.downloader import QUALITY_CHOICES
from app.utils.security import secure_file, settings_path

# Valores por defecto aplicados cuando no existe settings.json o falta una clave.
_DEFAULTS: dict[str, Any] = {
    "download_dir": str(Path.home() / "Downloads" / "RetroTube"),
    "default_quality": "1080",
    "default_format": "mp4",
    "rate_limit": "",
    "max_concurrent": 3,
    "browser": "chrome",
    "proxy": "",
    "cookies_file": "",
}

_FORMATS = ("mp4", "mkv", "webm", "mp3", "opus")


class SettingsManager:
    """Carga y guarda los ajustes de la aplicación en formato JSON."""

    def __init__(self) -> None:
        self._path = settings_path()
        self._data: dict[str, Any] = dict(_DEFAULTS)
        self.load()

    def load(self) -> dict[str, Any]:
        """Lee settings.json fusionándolo con los valores por defecto."""
        if self._path.is_file():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key in _DEFAULTS:
                        if key in raw:
                            self._data[key] = raw[key]
            except (OSError, json.JSONDecodeError):
                # Ante un archivo corrupto se conservan los valores por defecto.
                self._data = dict(_DEFAULTS)
        return dict(self._data)

    def save(self) -> None:
        """Escribe settings.json y le aplica permisos 600."""
        try:
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            secure_file(self._path)
        except OSError:
            # Un fallo de disco no debe derribar la aplicación.
            pass

    def get(self, key: str) -> Any:
        """Devuelve el valor de un ajuste (o su valor por defecto)."""
        return self._data.get(key, _DEFAULTS.get(key))

    def update(self, values: dict[str, Any]) -> None:
        """Actualiza varios ajustes a la vez y persiste el resultado."""
        for key, value in values.items():
            if key in _DEFAULTS:
                self._data[key] = value
        self.save()

    def as_dict(self) -> dict[str, Any]:
        """Copia del conjunto completo de ajustes."""
        return dict(self._data)


class SettingsScreen(QWidget):
    """Formulario visual para editar la configuración."""

    settings_saved = pyqtSignal(dict)

    def __init__(self, manager: SettingsManager) -> None:
        super().__init__()
        self._manager = manager
        self._build_ui()
        self._load_into_form()

    def _build_ui(self) -> None:
        """Construye el formulario de ajustes."""
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("CONFIGURACIÓN")
        title.setObjectName("ScreenTitle")
        root.addWidget(title)

        card = QFrame()
        card.setObjectName("Panel")
        form = QFormLayout(card)
        form.setContentsMargins(22, 22, 22, 22)
        form.setSpacing(14)

        # --- Carpeta de destino ---
        self._dir_edit = QLineEdit()
        browse = QPushButton("Examinar…")
        browse.setObjectName("GhostButton")
        browse.clicked.connect(self._choose_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse)
        dir_wrap = QWidget()
        dir_wrap.setLayout(dir_row)
        form.addRow("Carpeta destino:", dir_wrap)

        # --- Calidad por defecto ---
        self._quality = QComboBox()
        self._quality.addItems(QUALITY_CHOICES)
        form.addRow("Calidad por defecto:", self._quality)

        # --- Formato de salida ---
        self._format = QComboBox()
        self._format.addItems(_FORMATS)
        form.addRow("Formato:", self._format)

        # --- Límite de velocidad ---
        self._rate = QLineEdit()
        self._rate.setPlaceholderText("Ej. 500K o 2M (vacío = sin límite)")
        form.addRow("Velocidad máxima:", self._rate)

        # --- Descargas simultáneas ---
        self._concurrent = QSpinBox()
        self._concurrent.setRange(1, 5)
        form.addRow("Descargas simultáneas:", self._concurrent)

        # --- Navegador para cookies ---
        self._browser = QComboBox()
        self._browser.addItems(SUPPORTED_BROWSERS)
        form.addRow("Navegador (cookies):", self._browser)

        # --- Archivo de cookies opcional ---
        self._cookies = QLineEdit()
        self._cookies.setPlaceholderText(
            "Ruta a un cookies.txt (más fiable que leer del navegador)"
        )
        cookies_browse = QPushButton("Examinar…")
        cookies_browse.setObjectName("GhostButton")
        cookies_browse.clicked.connect(self._choose_cookies)
        cookies_row = QHBoxLayout()
        cookies_row.addWidget(self._cookies, 1)
        cookies_row.addWidget(cookies_browse)
        cookies_wrap = QWidget()
        cookies_wrap.setLayout(cookies_row)
        form.addRow("Archivo de cookies:", cookies_wrap)

        # --- Proxy opcional ---
        self._proxy = QLineEdit()
        self._proxy.setPlaceholderText("http://host:puerto o socks5://host:puerto")
        form.addRow("Proxy (opcional):", self._proxy)

        root.addWidget(card)

        note = QLabel(
            "Las cookies se leen del navegador en memoria. RetroTube nunca "
            "guarda usuario, contraseña ni tokens en disco."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        root.addWidget(note)

        save = QPushButton("Guardar configuración")
        save.clicked.connect(self._save)
        save.setFixedWidth(220)
        root.addWidget(save, alignment=Qt.AlignmentFlag.AlignRight)
        root.addStretch(1)

    def _choose_dir(self) -> None:
        """Abre un diálogo para elegir la carpeta de descargas."""
        current = self._dir_edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(
            self, "Selecciona la carpeta de descargas", current
        )
        if chosen:
            self._dir_edit.setText(chosen)

    def _choose_cookies(self) -> None:
        """Abre un diálogo para elegir un archivo cookies.txt."""
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Selecciona el archivo de cookies", str(Path.home()),
            "Cookies (*.txt);;Todos los archivos (*)"
        )
        if chosen:
            self._cookies.setText(chosen)

    def _load_into_form(self) -> None:
        """Vuelca los ajustes guardados en los controles del formulario."""
        self._dir_edit.setText(str(self._manager.get("download_dir")))
        self._quality.setCurrentText(str(self._manager.get("default_quality")))
        self._format.setCurrentText(str(self._manager.get("default_format")))
        self._rate.setText(str(self._manager.get("rate_limit")))
        self._concurrent.setValue(int(self._manager.get("max_concurrent")))
        self._browser.setCurrentText(str(self._manager.get("browser")))
        self._cookies.setText(str(self._manager.get("cookies_file")))
        self._proxy.setText(str(self._manager.get("proxy")))

    def _save(self) -> None:
        """Recoge el formulario, persiste los ajustes y emite la señal."""
        values: dict[str, Any] = {
            "download_dir": self._dir_edit.text().strip(),
            "default_quality": self._quality.currentText(),
            "default_format": self._format.currentText(),
            "rate_limit": self._rate.text().strip(),
            "max_concurrent": self._concurrent.value(),
            "browser": self._browser.currentText(),
            "cookies_file": self._cookies.text().strip(),
            "proxy": self._proxy.text().strip(),
        }
        self._manager.update(values)
        self.settings_saved.emit(self._manager.as_dict())


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    screen = SettingsScreen(SettingsManager())
    screen.resize(640, 560)
    screen.show()
    sys.exit(app.exec())
