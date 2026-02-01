@echo off
REM Script de ejemplo para importar fotos del iPhone
REM Modifica las rutas según tu configuración

echo ================================================
echo   iPhone Import - Importacion Automatica
echo ================================================
echo.

REM Configuración - MODIFICA ESTAS RUTAS
set IPHONE_PATH=Este equipo\Apple iPhone\Internal Storage
set DESTINO=D:\Iphone Exportar Totes Ordenades
set METADATA=D:\Iphone Exportar Totes Ordenades\.metadata

echo Origen: %IPHONE_PATH%
echo Destino: %DESTINO%
echo Metadata: %METADATA%
echo.

REM Verificar que Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado
    echo Por favor instala Python desde la Microsoft Store
    pause
    exit /b 1
)

echo Iniciando importacion...
echo.

REM Ejecutar el script de importación
python "%~dp0__main__.py" "%IPHONE_PATH%" "%DESTINO%" --metadata-folder "%METADATA%"

echo.
echo ================================================
echo   Importacion completada
echo ================================================
echo.
pause
