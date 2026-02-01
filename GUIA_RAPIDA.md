# 🚀 Guía Rápida - iPhone Import

## Instalación (Solo la primera vez)

```bash
cd C:\Users\Bernat\Downloads\iPhoneImport
pip install -r requirements.txt
```

## Uso Diario

### Opción 1: Usando el script BAT (Más fácil)

1. Edita `importar_iphone.bat` y ajusta las rutas
2. Conecta tu iPhone y desbloquéalo
3. Doble clic en `importar_iphone.bat`
4. ¡Listo!

### Opción 2: Desde PowerShell/CMD

```bash
cd C:\Users\Bernat\Downloads

# Importar todas las fotos organizadas por mes
python .\iPhoneImport "Este equipo\Apple iPhone\Internal Storage" "D:\iPhone\2025"

# Importar solo fotos nuevas (recomendado para uso diario)
python .\iPhoneImport "Este equipo\Apple iPhone\Internal Storage" "D:\iPhone\2025" --metadata-folder "D:\iPhone\.metadata"
```

## Estructura de Carpetas Resultante

```
D:\iPhone\2025\
├── 01-Gener\
│   ├── IMG_0001.jpg
│   └── VID_0002.mp4
├── 02-Febrer\
│   └── IMG_0050.jpg
├── 03-Març\
│   └── IMG_0100.jpg
...
└── 12-Desembre\
    └── IMG_9999.jpg
```

## ⚡ Consejos Pro

1. **Usa metadata-folder**: Evita copiar duplicados en futuras importaciones
2. **Conecta el iPhone**: Asegúrate de que esté desbloqueado y "confía en este ordenador"
3. **Backup regular**: Ejecuta el script semanalmente para no acumular fotos
4. **Verifica antes**: Usa `--skip-copy` para ver qué se copiará sin hacer cambios

## 🔧 Personalización

Edita `__main__.py` si quieres:
- Cambiar el idioma de los meses (líneas 20-33)
- Añadir más extensiones de archivo
- Modificar la lógica de organización

## ❓ Problemas Comunes

**"Cannot find Apple iPhone"**
→ Conecta el iPhone, desbloquéalo y confía en el PC

**"No module named 'PIL'"**
→ Ejecuta: `pip install Pillow`

**"PermissionError"**
→ Ejecuta PowerShell/CMD como administrador

**Archivos duplicados con _1, _2, etc.**
→ Es normal, significa que el archivo ya existe en destino

## 📞 Soporte

Para más detalles, consulta el `README.md` completo.
