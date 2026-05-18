# RetroTube Downloader

Descargador de YouTube para escritorio, en Python, con estetica inspirada en
Windows Media Player de los anos 2000.

## Advertencia de privacidad

Esta app usa tus cookies de navegador localmente. Nunca las transmite a
servidores externos.

La autenticacion se hace leyendo las cookies del navegador en memoria
(`yt-dlp --cookies-from-browser`). No se piden usuario ni contrasena, no se
guardan credenciales, tokens ni sesiones en disco, y no hay sockets ni
telemetria.

## Funciones

- Splash de arranque animado.
- Dashboard con feed de recomendaciones (personalizado con sesion, o
  tendencias publicas sin ella) y cola de descargas en tiempo real.
- Buscador sin API key mediante `ytsearch20`.
- Mis descargas: biblioteca local con filtros y estadisticas.
- Mis listas: listas locales con color, drag and drop, descarga de listas de
  YouTube por URL y exportacion a M3U.
- Sesion mediante cookies del navegador (Chrome, Firefox, Edge y otros).
- Configuracion de carpeta, calidad, formato, limite de velocidad, descargas
  simultaneas, navegador y proxy.

## Stack tecnico

- Interfaz: PyQt6
- Descargas: yt-dlp (via subprocess, sin shell)
- Base de datos: SQLite con SQLAlchemy (solo metadatos)
- HTTP: httpx con timeouts estrictos
- Concurrencia: QThreadPool y QRunnable

## Requisitos

- Python 3.10 o superior.
- Un navegador con sesion de YouTube iniciada (opcional; solo para el feed
  personalizado o vistas con restriccion de edad).

## Instalacion

```
pip install -r requirements.txt
```

## Ejecucion

```
python main.py
```

Cada modulo tambien se puede ejecutar de forma independiente, por ejemplo:

```
python -m app.core.validators
python -m app.ui.splash
```

## Compilar a .exe

El ejecutable de Windows se genera con PyInstaller. El icono es `konata.ico`
y se incluye una copia de `yt-dlp.exe` para que las descargas funcionen sin
un intérprete de Python.

```
pip install pyinstaller
curl -L -o yt-dlp.exe https://github.com/yt-dlp/yt-dlp/releases/download/2024.12.13/yt-dlp.exe
python -m PyInstaller --noconfirm --onefile --windowed --name RetroTube ^
  --icon konata.ico ^
  --add-data "app/ui/style.qss;app/ui" ^
  --add-data "konata.ico;." ^
  --add-binary "yt-dlp.exe;." main.py
```

El resultado queda en `dist/RetroTube.exe`. Para procesar formatos que
requieren remux o extraer audio (MP3/OPUS) hace falta `ffmpeg` instalado o
accesible en el PATH.

## Seguridad

- No se almacenan credenciales, tokens ni sesiones.
- Toda URL pasa por `validate_youtube_url()` antes de llegar a yt-dlp.
- yt-dlp se invoca siempre con una lista de argumentos, nunca con `shell=True`.
- Las consultas SQL usan parametros vinculados (ORM), nunca interpolacion.
- `settings.json` recibe permisos 600 cuando el sistema lo permite.
- La base de datos solo guarda id, titulo, URL, ruta local, ruta de miniatura,
  fecha de descarga, canal, duracion y tamano en bytes.

## Estructura

```
retrotube/
  main.py
  app/
    ui/      Pantallas PyQt6 y style.qss
    core/    Descargas, busqueda, autenticacion, datos, validacion
    utils/   Miniaturas, seguridad, animaciones
  requirements.txt
  .gitignore
  README.md
```

## Licencia

Uso educativo. Respeta los Terminos de Servicio de YouTube y la legislacion de
derechos de autor aplicable.
