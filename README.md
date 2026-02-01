# iPhoneImport - Importación Automática con Organización por Meses

Script de Python mejorado para copiar y **organizar automáticamente** fotos y videos desde tu iPhone a tu PC Windows, organizándolos por **año y mes en catalán**.

## ✨ Características Principales

- 🗂️ **Organización automática** por año y mes (2025/01-Gener, 02-Febrer, etc.)
- 📸 **Solo archivos multimedia**: Filtra automáticamente fotos y videos
- 📅 **Extracción inteligente de fechas**: Usa metadatos EXIF cuando están disponibles
- 🔄 **Evita duplicados**: Detecta archivos ya importados
- 💪 **Ultra robusto**: Manejo extensivo de errores, nunca falla
- 🎯 **Nombres únicos**: Si existe un archivo, añade un número automáticamente
- 🇪🇸 **Meses en catalán**: Gener, Febrer, Març, Abril, Maig, Juny, etc.

## 📋 Formatos Soportados

**Imágenes:** JPG, JPEG, PNG, GIF, BMP, TIFF, HEIC, HEIF, RAW, CR2, NEF, ARW, DNG, WebP
**Videos:** MP4, MOV, AVI, MKV, M4V, 3GP, WMV, FLV, WebM, MPEG

## 🚀 Instalación

1. **Instalar Python 3.10+** desde la Microsoft Store
2. **Instalar dependencias:**

```bash
pip install -r requirements.txt
```

O manualmente:

```bash
pip install pywin32 Pillow
```

## 📖 Uso

### Importación básica con organización automática

Copia todas las fotos/videos del iPhone y las organiza por año y mes:

```bash
python C:\Users\Bernat\Downloads\iPhoneImport "Este equipo\Apple iPhone\Internal Storage" "D:\iPhone\2025"
```

Esto creará una estructura como:
```
D:\iPhone\2025\
├── 01-Gener\
│   ├── IMG_0001.jpg
│   └── IMG_0002.heic
├── 02-Febrer\
│   ├── IMG_0050.jpg
│   └── VID_0051.mp4
└── 03-Març\
    └── IMG_0100.jpg
```

### Importación incremental (solo archivos nuevos)

Evita copiar archivos ya importados usando una carpeta de metadatos:

```bash
python C:\Users\Bernat\Downloads\iPhoneImport "Este equipo\Apple iPhone\Internal Storage" "D:\iPhone\2025" --metadata-folder "D:\iPhone\metadata"
```

### Modo simulación (dry-run)

Ver qué archivos se importarían sin copiarlos realmente:

```bash
python C:\Users\Bernat\Downloads\iPhoneImport "Este equipo\Apple iPhone\Internal Storage" "D:\iPhone\2025" --skip-copy
```

### Sin organización automática

Si prefieres mantener la estructura original del iPhone:

```bash
python C:\Users\Bernat\Downloads\iPhoneImport "Este equipo\Apple iPhone\Internal Storage" "D:\iPhone\2025" --no-organize
```

## 🛠️ Opciones Disponibles

| Opción | Descripción |
|--------|-------------|
| `source` | Ruta del iPhone (ej: "Este equipo\Apple iPhone\Internal Storage") |
| `destination` | Carpeta destino donde se guardarán las fotos |
| `--metadata-folder` | Carpeta para registrar archivos ya importados (evita duplicados) |
| `--skip-copy` | Modo simulación: no copia archivos, solo muestra lo que haría |
| `--no-organize` | Desactiva la organización por fecha, mantiene estructura original |

## 💡 Ejemplos Prácticos

**Importación completa del año 2025:**
```bash
python __main__.py "Este equipo\Apple iPhone\Internal Storage" "D:\Fotos\2025"
```

**Importación incremental con backup de metadatos:**
```bash
python __main__.py "Este equipo\Apple iPhone\Internal Storage" "D:\Fotos\2025" --metadata-folder "D:\Fotos\.metadata"
```

**Ver qué archivos nuevos hay sin copiarlos:**
```bash
python __main__.py "Este equipo\Apple iPhone\Internal Storage" "D:\Fotos\2025" --skip-copy --metadata-folder "D:\Fotos\.metadata"
```

## 🔧 Cómo Funciona

1. **Conexión**: El script accede al iPhone mediante Windows Shell API
2. **Escaneo**: Recorre todas las carpetas DCIM del dispositivo
3. **Filtrado**: Identifica solo archivos multimedia (fotos/videos)
4. **Extracción de fecha**: Intenta obtener la fecha desde:
   - Metadatos EXIF de la imagen (preferido)
   - Nombre del archivo si contiene fecha
   - Fecha actual como fallback
5. **Organización**: Crea carpetas YYYY/MM-Mes en catalán
6. **Copia**: Usa operaciones de Shell para copiar archivos de forma eficiente
7. **Registro**: Guarda lista de archivos importados para evitar duplicados

## ⚠️ Notas Importantes

- **Conecta tu iPhone** antes de ejecutar el script
- **Desbloquea el iPhone** y confía en el ordenador cuando se te pida
- El script **copia** archivos, no los mueve (tus fotos quedan en el iPhone)
- Si hay errores de permisos, ejecuta el terminal como administrador
- La extracción de EXIF funciona mejor con JPG; HEIC puede tener limitaciones

## 📁 Estructura del Proyecto

```
iPhoneImport/
├── __main__.py           # Script principal (¡mejorado!)
├── win32utils.py         # Utilidades de Windows Shell
├── requirements.txt      # Dependencias Python
├── consolidate_photos.py # Script adicional para consolidar carpetas
└── README.md            # Esta documentación
```

## 🎁 Script Adicional: Consolidador de Fotos

Si ya tienes fotos en múltiples carpetas y quieres juntarlas todas:

```bash
python consolidate_photos.py "D:\Test Iphone" "D:\Todas_las_fotos"
```

## 🐛 Solución de Problemas

**Error: "Cannot find Apple iPhone"**
- Asegúrate de que el iPhone esté conectado y desbloqueado
- Verifica que iTunes o el controlador de Apple esté instalado

**No se copian algunos archivos:**
- Algunos formatos HEIC pueden requerir códecs adicionales
- Verifica permisos de escritura en la carpeta destino

**Error de metadatos EXIF:**
- El script continuará usando la fecha del nombre del archivo
- Instala la última versión de Pillow: `pip install --upgrade Pillow`

## 📝 Licencia

Este proyecto mantiene la licencia original. Consulta el archivo LICENSE para más detalles.

## 🙏 Créditos

Script original por el autor de iPhoneImport
Mejoras y organización automática: 2026
