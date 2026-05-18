"""Ventana principal de RetroTube Downloader.

Integra el menú de navegación, las pantallas apiladas, el panel de cola de
descargas y la barra de estado con el indicador de sesión. Coordina además
los gestores de datos, descargas, autenticación y miniaturas.
"""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import __app_name__, __version__
from app.core.auth import SUPPORTED_BROWSERS, AuthManager
from app.core.database import Database
from app.core.downloader import DownloadManager, DownloadTask
from app.ui.dashboard import DashboardScreen
from app.ui.downloads import DownloadsScreen
from app.ui.playlists import PlaylistsScreen
from app.ui.queue_panel import QueuePanel
from app.ui.search import SearchScreen
from app.ui.settings import SettingsManager, SettingsScreen
from app.utils.animations import fade_in
from app.utils.thumbnails import ThumbnailManager, cached_path

# Contenedores de vídeo válidos (los formatos de audio se tratan aparte).
_VIDEO_CONTAINERS = ("mp4", "mkv", "webm")


class SessionScreen(QWidget):
    """Pantalla de sesión: verificación de cookies y cierre de sesión."""

    def __init__(
        self, auth_manager: AuthManager, settings_manager: SettingsManager
    ) -> None:
        super().__init__()
        self._auth = auth_manager
        self._settings = settings_manager
        self._build_ui()
        self._auth.auth_changed.connect(self._on_auth_changed)
        self._auth.auth_error.connect(
            lambda msg: self._status.setText(f"Aviso: {msg}")
        )

    def _build_ui(self) -> None:
        """Construye la disposición de la pantalla de sesión."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("SESIÓN")
        title.setObjectName("ScreenTitle")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("Panel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(12)

        explain = QLabel(
            "RetroTube se autentica usando las cookies de tu navegador. "
            "Nunca se pide usuario ni contraseña, y las cookies jamás se "
            "guardan en disco ni se envían a ningún servidor externo."
        )
        explain.setObjectName("Muted")
        explain.setWordWrap(True)
        card_layout.addWidget(explain)

        self._status = QLabel("Estado: sin sesión")
        self._status.setStyleSheet(
            "font-family:'Courier New';color:#33CCFF;font-size:15px;"
        )
        card_layout.addWidget(self._status)

        buttons = QHBoxLayout()
        verify = QPushButton("Verificar sesión")
        verify.clicked.connect(self._verify)
        logout = QPushButton("Cerrar sesión")
        logout.setObjectName("DangerButton")
        logout.clicked.connect(self._logout)
        buttons.addWidget(verify)
        buttons.addWidget(logout)
        buttons.addStretch(1)
        card_layout.addLayout(buttons)

        layout.addWidget(card)
        layout.addStretch(1)

    def _verify(self) -> None:
        """Verifica la sesión con el navegador configurado."""
        browser = self._settings.get("browser")
        if browser not in SUPPORTED_BROWSERS:
            browser = "chrome"
        self._auth.set_browser(browser)
        self._status.setText(f"Verificando con {browser}…")
        self._auth.verify(self._settings.get("proxy") or None)

    def _logout(self) -> None:
        """Cierra la sesión y limpia la caché temporal de yt-dlp."""
        self._auth.logout()
        self._status.setText("Estado: sesión cerrada.")

    def _on_auth_changed(self, authenticated: bool, name: str) -> None:
        """Actualiza el texto de estado al cambiar la sesión."""
        if authenticated:
            self._status.setText(f"Estado: sesión activa como {name}")
        else:
            self._status.setText("Estado: sin sesión")


class MainWindow(QWidget):
    """Ventana principal de la aplicación."""

    closing = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.resize(1280, 760)

        # --- Gestores compartidos ---
        self.settings = SettingsManager()
        self.database = Database()
        self.auth = AuthManager()
        self.auth.set_browser(self.settings.get("browser"))
        self.thumbnails = ThumbnailManager()
        self.downloads_mgr = DownloadManager(
            int(self.settings.get("max_concurrent"))
        )
        # Metadatos en memoria de las descargas en curso (id -> dict).
        self._active: dict[str, dict] = {}

        self._build_ui()
        self._connect_signals()

        # El dashboard queda seleccionado al arrancar.
        self._nav_group.button(0).setChecked(True)
        self.stack.setCurrentIndex(0)

        # Primera carga del feed (como visitante hasta verificar sesión).
        self.dashboard.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Construye la disposición de tres zonas de la ventana."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        body.addWidget(self._build_nav())
        body.addWidget(self._build_stack(), 1)
        body.addWidget(self._build_queue())
        root.addLayout(body, 1)
        root.addWidget(self._build_status_bar())

    def _build_nav(self) -> QWidget:
        """Crea el panel de navegación lateral izquierdo."""
        panel = QFrame()
        panel.setObjectName("BevelTop")
        panel.setFixedWidth(212)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(6)

        brand = QLabel("▶ RetroTube")
        brand.setStyleSheet(
            "font-size:18px;font-weight:bold;color:#33CCFF;padding:6px;"
        )
        layout.addWidget(brand)
        layout.addSpacing(10)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        entries = (
            ("▦  Dashboard", 0),
            ("⌕  Buscar", 1),
            ("▼  Mis descargas", 2),
            ("☰  Mis listas", 3),
            ("⚿  Sesión", 4),
            ("⚙  Configuración", 5),
        )
        for text, index in entries:
            button = QPushButton(text)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _c, i=index: self._navigate(i))
            self._nav_group.addButton(button, index)
            layout.addWidget(button)

        layout.addStretch(1)
        version = QLabel(f"v{__version__}")
        version.setObjectName("Muted")
        version.setStyleSheet("font-family:'Courier New';padding:4px;")
        layout.addWidget(version)
        return panel

    def _build_stack(self) -> QWidget:
        """Crea el contenedor apilado con todas las pantallas."""
        self.stack = QStackedWidget()

        self.dashboard = DashboardScreen(
            self.thumbnails, self.settings, self.auth
        )
        self.search = SearchScreen(self.thumbnails, self.settings)
        self.downloads_screen = DownloadsScreen(self.database)
        self.playlists = PlaylistsScreen(self.database, self.settings)
        self.session = SessionScreen(self.auth, self.settings)
        self.settings_screen = SettingsScreen(self.settings)

        for screen in (
            self.dashboard, self.search, self.downloads_screen,
            self.playlists, self.session, self.settings_screen,
        ):
            self.stack.addWidget(screen)
        return self.stack

    def _build_queue(self) -> QWidget:
        """Crea el panel derecho con la cola de descargas."""
        wrapper = QFrame()
        wrapper.setObjectName("Panel")
        wrapper.setFixedWidth(328)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(4, 4, 4, 4)
        self.queue = QueuePanel()
        layout.addWidget(self.queue)
        return wrapper

    def _build_status_bar(self) -> QWidget:
        """Crea la barra de estado con el indicador de sesión."""
        bar = QFrame()
        bar.setObjectName("BevelTop")
        bar.setFixedHeight(30)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 2, 12, 2)

        self._lock = QLabel("🔒 Sin sesión")
        self._lock.setStyleSheet("color:#FFCC33;font-family:'Courier New';")
        layout.addWidget(self._lock)
        layout.addStretch(1)

        self._status_label = QLabel("Listo.")
        self._status_label.setObjectName("Muted")
        self._status_label.setStyleSheet("font-family:'Courier New';")
        layout.addWidget(self._status_label)
        return bar

    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Conecta las señales entre pantallas y gestores."""
        # Solicitudes de descarga procedentes de las distintas pantallas.
        self.dashboard.download_requested.connect(self._start_download)
        self.search.download_requested.connect(self._start_download)
        self.playlists.download_requested.connect(self._start_download)

        # Mensajes de estado.
        for screen in (
            self.dashboard, self.search, self.downloads_screen, self.playlists
        ):
            screen.status_message.connect(self._set_status)

        # Cancelaciones desde el panel de cola.
        self.queue.cancel_requested.connect(self.downloads_mgr.cancel)

        # Eventos del gestor de descargas.
        self.downloads_mgr.task_progress.connect(self.queue.update_progress)
        self.downloads_mgr.task_finished.connect(self._on_download_finished)
        self.downloads_mgr.task_failed.connect(self._on_download_failed)

        # Cambios de sesión y de configuración.
        self.auth.auth_changed.connect(self._on_auth_changed)
        self.settings_screen.settings_saved.connect(self._on_settings_saved)

    # ------------------------------------------------------------------
    def _navigate(self, index: int) -> None:
        """Cambia de pantalla aplicando una transición de aparición."""
        self.stack.setCurrentIndex(index)
        fade_in(self.stack.currentWidget(), 280)

    def _set_status(self, message: str) -> None:
        """Actualiza el texto de la barra de estado."""
        self._status_label.setText(message)

    def _resolve_container(self, quality: str) -> str:
        """Determina el contenedor de salida según la calidad pedida."""
        if quality.startswith("audio_"):
            return "mp4"  # Irrelevante: la descarga será solo de audio.
        fmt = str(self.settings.get("default_format"))
        return fmt if fmt in _VIDEO_CONTAINERS else "mp4"

    def _start_download(self, video: dict, quality: str) -> None:
        """Crea y encola una tarea de descarga para un vídeo."""
        task_id = video["id"]
        if task_id in self._active:
            self._set_status("Ese vídeo ya está en la cola.")
            return

        # Las cookies solo se usan si hay sesión verificada.
        browser = self.auth.browser if self.auth.authenticated else None
        try:
            task = DownloadTask(
                task_id=task_id,
                url=video["url"],
                output_dir=str(self.settings.get("download_dir")),
                quality=quality,
                container=self._resolve_container(quality),
                browser=browser,
                proxy=self.settings.get("proxy") or None,
                rate_limit=self.settings.get("rate_limit") or None,
            )
        except ValueError as exc:
            self._set_status(f"URL rechazada: {exc}")
            return

        self._active[task_id] = video
        self.queue.add_item(
            task_id, video.get("title", ""), video.get("channel", "")
        )
        # Precarga la miniatura para tenerla disponible en "Mis descargas".
        self.thumbnails.request(task_id, video.get("thumbnail", ""))
        self.downloads_mgr.enqueue(task)
        self._set_status(f"Descarga añadida: {video.get('title', '')}")

    def _on_download_finished(
        self, task_id: str, path: str, size: int
    ) -> None:
        """Registra la descarga completada en la base de datos."""
        video = self._active.pop(task_id, None)
        self.queue.mark_finished(task_id)
        if video is None:
            return
        thumb = cached_path(task_id)
        self.database.upsert_download({
            "id": task_id,
            "title": video.get("title", ""),
            "url": video.get("url", ""),
            "local_path": path,
            "thumbnail_path": str(thumb) if thumb.is_file() else "",
            "channel": video.get("channel", ""),
            "duration": int(video.get("duration", 0) or 0),
            "size_bytes": int(size),
        })
        self.downloads_screen.refresh()
        self._set_status(f"Descarga completada: {video.get('title', '')}")

    def _on_download_failed(self, task_id: str, message: str) -> None:
        """Refleja un fallo de descarga en la cola y la barra de estado."""
        self._active.pop(task_id, None)
        self.queue.mark_failed(task_id, message)
        self._set_status(f"Descarga fallida: {message}")

    def _on_auth_changed(self, authenticated: bool, name: str) -> None:
        """Actualiza el indicador de sesión y recarga el feed."""
        if authenticated:
            self._lock.setText(f"🔒 Sesión: {name}")
            self._lock.setStyleSheet(
                "color:#33FF88;font-family:'Courier New';"
            )
        else:
            self._lock.setText("🔓 Sin sesión")
            self._lock.setStyleSheet(
                "color:#FFCC33;font-family:'Courier New';"
            )
        # El feed se recarga para reflejar el nuevo estado de sesión.
        self.dashboard.refresh()

    def _on_settings_saved(self, values: dict) -> None:
        """Aplica los ajustes guardados a los gestores en caliente."""
        self.auth.set_browser(values.get("browser", "chrome"))
        self.downloads_mgr.set_max_concurrent(
            int(values.get("max_concurrent", 3))
        )
        self._set_status("Configuración guardada.")

    def closeEvent(self, event) -> None:  # noqa: N802 - API de Qt.
        """Cancela las descargas activas y libera recursos al cerrar."""
        self.downloads_mgr.cancel_all()
        self.database.dispose()
        self.closing.emit()
        super().closeEvent(event)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    app = QApplication(sys.argv)
    qss = Path(__file__).with_name("style.qss")
    if qss.is_file():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
