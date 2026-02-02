# iImport (baseline)

Aplicación Windows portable (PySide6) para importar fotos y vídeos desde un iPhone por USB en Windows 10/11 (x64). No requiere instalación ni permisos de administrador y se distribuye como carpeta onedir (PyInstaller).

## Requisitos de desarrollo
- Windows 10/11
- Python 3.11+
- Dependencias: `pip install -r requirements.txt`

## Ejecutar en desarrollo
```bat
python src\main.py
```

## Build (onedir)
```bat
build.bat
```
El resultado queda en `dist\iImport\`.

## Herramientas opcionales (conversión)
Si quieres habilitar “Crear copias compatibles”, coloca los binarios aquí:
- `tools\ffmpeg.exe`
- `tools\exiftool.exe`

Luego vuelve a ejecutar `build.bat` o copia la carpeta `tools` dentro del `dist\iImport\`.

## Portable data layout
- **Config**: `config.json` junto al `.exe` (idioma, estructura, última carpeta, opciones).
- **Caché**: `_cache\` junto al `.exe` (comtypes, escaneo).
- **Temporales**: `Destino\.tmp_import\` durante la importación.
- **Logs**: `Destino\iImport_logs\import_YYYYMMDD_HHMMSS.log`.
- No se usa AppData por lógica propia de la app.

## Troubleshooting
Ver `docs\TROUBLESHOOTING.md`.
Guía rápida: `docs\GUIA_RAPIDA.md`.

## Tests
```bat
pytest
```

## Estructura
```
/src
  /domain
  /application
  /infrastructure
  /ui
/tests
```
