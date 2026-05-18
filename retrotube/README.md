# RetroTube Downloader

Descargador profesional de YouTube para escritorio con estética inspirada en
**Windows Media Player** (era 2000s): fondos azul-negro profundo, acentos en
azul cian brillante, bordes biselados tipo *gloss*, tipografía LCD y
animaciones de transición exageradas.

---

## ⚠️ Advertencia de privacidad

> **Esta app usa tus cookies de navegador localmente. Nunca las transmite a
> servidores externos.**

RetroTube se autentica leyendo las cookies de tu navegador en memoria
(`yt-dlp --cookies-from-browser`). **Nunca** solicita usuario ni contraseña,
**nunca** guarda credenciales, tokens ni sesiones en disco, y **no** abre
sockets ni envía telemetría.

---

## Características

- **Splash animado** con efecto *scan line* y barra de progreso LED.
- **Dashboard** con feed de recomendaciones (personalizado si hay sesión, o
  tendencias públicas si no) y cola de descargas en tiempo real.
- **Buscador** sin API key mediante `ytsearch20`, con rejilla de tarjetas y
  selector de calidad (144p → 4K, además de audio MP3/OPUS).
- **Mis descargas**: biblioteca local con filtros, estadísticas y gestión de
  archivos.
- **Mis listas**: listas locales con color, *drag & drop*, descarga de listas
  de YouTube por URL y exportación a M3U.
- **Sesión** mediante cookies del navegador (Chrome / Firefox / Edge…).
- **Configuración** de carpeta, calidad, formato, límite de velocidad,
  descargas simultáneas, navegador y proxy.

## Stack técnico

| Componente        | Tecnología                          |
|-------------------|-------------------------------------|
| Interfaz gráfica  | PyQt6                               |
| Descargas         | yt-dlp (vía `subprocess`, sin shell)|
| Base de datos     | SQLite + SQLAlchemy (solo metadatos)|
| Peticiones HTTP   | httpx (con *timeouts* estrictos)    |
| Concurrencia      | QThreadPool + QRunnable             |

## Requisitos

- Python 3.10 o superior.
- Un navegador compatible con sesión de YouTube iniciada (opcional, solo si
  quieres feed personalizado o vídeos con restricción de edad).

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
python main.py
```

Cada módulo es además ejecutable de forma independiente para pruebas, por
ejemplo:

```bash
python -m app.core.validators
python -m app.ui.splash
```

## Seguridad

- Cero almacenamiento de credenciales, tokens o sesiones.
- Toda URL pasa por `validate_youtube_url()` con expresiones regulares
  estrictas antes de llegar a `yt-dlp`.
- `yt-dlp` se invoca siempre con una lista de argumentos, nunca con
  `shell=True`.
- Todas las consultas SQL usan parámetros vinculados (ORM), nunca
  interpolación de cadenas.
- `settings.json` recibe permisos `600` cuando el sistema operativo lo
  permite.
- La base de datos SQLite solo guarda: id, título, URL, ruta local, ruta de
  miniatura, fecha de descarga, canal, duración y tamaño en bytes.

## Estructura del proyecto

```
retrotube/
├── main.py
├── app/
│   ├── ui/        Pantallas PyQt6 + style.qss
│   ├── core/      Descargas, búsqueda, autenticación, datos, validación
│   └── utils/     Miniaturas, seguridad, animaciones
├── requirements.txt
├── .gitignore
└── README.md
```

## Licencia

Uso educativo. Respeta los Términos de Servicio de YouTube y la legislación
de derechos de autor aplicable en tu país.
