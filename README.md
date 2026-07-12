# TikTok Downloader

Aplicación de escritorio para macOS que descarga videos de TikTok y transcribe su audio a texto usando inteligencia artificial.

---

## Funcionalidades

### Descargar Video
- Pega el link de cualquier video público de TikTok
- Selecciona la carpeta donde guardarlo
- Descarga el video en la **mejor calidad disponible** (video + audio, formato MP4)
- Incrusta miniatura y metadatos automáticamente
- Usa **impersonación de navegador** para evitar bloqueos de TikTok
- Si falla por restricciones de red, reintenta automáticamente sin impersonación

### Descargar Guión (Transcripción)
- Toma el mismo link de TikTok
- Descarga el audio en máxima calidad (WAV)
- Lo transcribe con **Whisper** (OpenAI) — modelo seleccionable
- Genera un archivo `.txt` con timestamps y el texto completo
- Soporta modelos: tiny (rápido), base, small, medium, large, turbo (preciso)

### Actualizaciones Automáticas
- Al iniciar, verifica contra PyPI si hay versiones nuevas de las dependencias
- Si hay actualizaciones, te pregunta si deseas descargarlas
- Las instala automáticamente desde la interfaz

---

## Requisitos

- **macOS 14+** (probado en macOS 26)
- **Homebrew** (para instalar Python 3.14+ y ffmpeg)
- Conexión a internet

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/tiktok-downloader.git
cd tiktok-downloader
```

### 2. Instalar dependencias del sistema

```bash
brew install python@3.14 ffmpeg
brew install python-tk@3.14
```

### 3. Crear y activar el entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Instalar dependencias de Python

```bash
pip install --upgrade pip
pip install yt-dlp openai-whisper curl_cffi
```

### 5. Ejecutar

```bash
python3 tiktok_downloader.py
```

O abre **TikTok Downloader.app** directamente (si lo moviste a Aplicaciones).

---

## Uso

1. Abre la aplicación
2. **Pestaña "Descargar Video"**: pega el link de TikTok, elige destino, presiona el botón
3. **Pestaña "Descargar Guión"**: pega el link, elige el modelo de Whisper (base recomendado), presiona el botón
4. El progreso se muestra en el panel de log
5. Al terminar, aparece una notificación y el archivo está listo en la carpeta de destino

### Atajos y opciones

| Acción | Cómo |
|---|---|
| Cambiar carpeta destino | Botón "Examinar" |
| Abrir carpeta en Finder | Botón "Abrir" |
| Verificar actualizaciones | Menú Archivo → Buscar actualizaciones |
| Carpeta por defecto | `~/Downloads/TikTok Downloads/` |

---

## Solución de problemas

### "ffprobe and ffmpeg not found"

```bash
which ffmpeg
# Si no aparece, instálalo:
brew install ffmpeg
# Si aparece en /opt/homebrew/bin, la app ya lo encuentra automáticamente
```

### "Could not resolve host: www.tiktok.com"

Error de red/DNS. La app reintenta automáticamente sin impersonación. Si persiste:
- Revisa tu conexión a internet
- Prueba con otro video
- Algunos videos privados o regionales no son accesibles

### La ventana se queda en negro

Ocurre si ejecutas la app con Python 3.9 del sistema (Tk 8.5). Solución:
```bash
# Usa Python 3.14+ con Tk 9.0
brew install python@3.14 python-tk@3.14
```

### La transcripción no encuentra el audio

El comando `--print after_move:filename` devuelve el nombre real después de la conversión a WAV. Si aún falla, la app busca el archivo `.wav` más reciente en la carpeta de destino como respaldo.

---

## Estructura del proyecto

```
tiktok-downloader/
├── tiktok_downloader.py      # Aplicación principal
├── TikTokDownloader.app/     # Bundle nativo de macOS
│   └── Contents/
│       ├── Info.plist
│       ├── MacOS/
│       │   └── TikTokDownloader      # Lanzador
│       └── Resources/
│           ├── tiktok_downloader.py  # Código fuente
│           ├── AppIcon.icns          # Icono de la app
│           └── venv/                 # Entorno virtual
├── lanzar_tiktok.sh          # Lanzador alternativo
├── README.md                 # Este archivo
└── LICENSE
```

---

## Tecnologías

| Componente | Tecnología |
|---|---|
| Interfaz gráfica | Python tkinter + ttk (Tk 9.0) |
| Descarga de video | [yt-dlp](https://github.com/yt-dlp/yt-dlp) con impersonación curl_cffi |
| Transcripción | [OpenAI Whisper](https://github.com/openai/whisper) |
| Procesamiento de audio | ffmpeg |
| Actualizaciones | PyPI JSON API + pip |

---

## Licencia

Uso personal y educativo.

---

**Walter García Ortiz**
Comentarios y sugerencias: walter.garciaortiz@gmail.com
Julio 2026
