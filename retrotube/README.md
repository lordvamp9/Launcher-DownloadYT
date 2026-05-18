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

## Inicio de sesion y descargas

YouTube exige cookies de una cuenta para descargar la mayoria de los videos
(control "Sign in to confirm you're not a bot"). Buscar y explorar funciona
sin sesion, pero para descargar conviene iniciar sesion.

En la pestana Sesion se elige el navegador y se pulsa Verificar sesion.
Importante: Chrome y Edge bloquean su base de datos de cookies mientras estan
abiertos, asi que hay que **cerrarlos por completo** antes de verificar.

Metodo mas fiable: exportar un archivo `cookies.txt` con una extension del
navegador (por ejemplo "Get cookies.txt LOCALLY") e indicar su ruta en la
pestana Sesion o en Configuracion. La app solo guarda la ruta del archivo,
nunca su contenido.

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

## Descarga del ejecutable

En la pestana Releases del repositorio hay un `RetroTube.exe` listo para usar
en Windows de 64 bits. Es autonomo: incluye `yt-dlp` y `ffmpeg`, asi que no
necesita instalar Python ni dependencias.

## Compilar a .exe

El ejecutable se genera con PyInstaller en modo onefile. El icono es
`konata.ico` y se incluyen `yt-dlp.exe`, `ffmpeg.exe` y `ffprobe.exe` para
que las descargas, el remux y la extraccion de audio funcionen sin requisitos
externos.

```
pip install pyinstaller
curl -L -o yt-dlp.exe https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
:: Descarga ffmpeg.exe y ffprobe.exe (build estatico de Windows) en esta carpeta
python -m PyInstaller --noconfirm --onefile --windowed --name RetroTube ^
  --icon konata.ico ^
  --add-data "app/ui/style.qss;app/ui" ^
  --add-data "konata.ico;." ^
  --add-binary "yt-dlp.exe;." ^
  --add-binary "ffmpeg.exe;." ^
  --add-binary "ffprobe.exe;." main.py
```

El resultado queda en `dist/RetroTube.exe`. Al ejecutar desde el codigo
fuente, si colocas `ffmpeg.exe` en la raiz del proyecto la app lo detecta
automaticamente; si no, usa el `ffmpeg` del PATH del sistema.

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
