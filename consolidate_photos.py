"""
Script para consolidar todas las fotos de múltiples carpetas en una sola carpeta.
"""
import os
import shutil
from pathlib import Path
from typing import Set

# Extensiones de archivo de imagen comunes
IMAGE_EXTENSIONS: Set[str] = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.heic', '.heif', '.raw', '.cr2', '.nef', '.arw', '.dng',
    '.webp', '.ico'
}

def consolidate_photos(source_dir: str, destination_dir: str, copy_files: bool = True):
    """
    Consolida todas las fotos de las subcarpetas en una sola carpeta.
    
    Args:
        source_dir: Directorio con las carpetas que contienen fotos
        destination_dir: Carpeta destino donde se copiarán todas las fotos
        copy_files: Si True copia archivos, si False los mueve
    """
    source_path = Path(source_dir)
    dest_path = Path(destination_dir)
    
    # Crear carpeta destino si no existe
    dest_path.mkdir(parents=True, exist_ok=True)
    
    total_files = 0
    copied_files = 0
    skipped_files = 0
    errors = 0
    
    print(f"Buscando fotos en: {source_path}")
    print(f"Destino: {dest_path}")
    print(f"Operación: {'Copiar' if copy_files else 'Mover'}")
    print("-" * 60)
    
    # Recorrer todas las subcarpetas
    for root, dirs, files in os.walk(source_path):
        for filename in files:
            file_path = Path(root) / filename
            extension = file_path.suffix.lower()
            
            # Verificar si es una imagen
            if extension in IMAGE_EXTENSIONS:
                total_files += 1
                dest_file = dest_path / filename
                
                # Si el archivo ya existe, agregar un número al nombre
                if dest_file.exists():
                    base_name = dest_file.stem
                    counter = 1
                    while dest_file.exists():
                        new_name = f"{base_name}_{counter}{extension}"
                        dest_file = dest_path / new_name
                        counter += 1
                
                try:
                    if copy_files:
                        shutil.copy2(file_path, dest_file)
                    else:
                        shutil.move(str(file_path), str(dest_file))
                    
                    copied_files += 1
                    if copied_files % 100 == 0:
                        print(f"Procesados {copied_files} archivos...")
                        
                except Exception as e:
                    print(f"Error procesando {file_path}: {e}")
                    errors += 1
    
    print("-" * 60)
    print(f"\n✓ Proceso completado!")
    print(f"  Total de fotos encontradas: {total_files}")
    print(f"  Fotos {'copiadas' if copy_files else 'movidas'}: {copied_files}")
    print(f"  Archivos omitidos: {skipped_files}")
    print(f"  Errores: {errors}")
    print(f"\nTodas las fotos están en: {dest_path}")


if __name__ == "__main__":
    import sys
    
    # Configuración por defecto
    SOURCE_DIR = r"D:\Test Iphone"
    DESTINATION_DIR = r"D:\Test Iphone\Todas_las_fotos"
    
    # Permitir pasar argumentos por línea de comandos
    if len(sys.argv) >= 2:
        SOURCE_DIR = sys.argv[1]
    if len(sys.argv) >= 3:
        DESTINATION_DIR = sys.argv[2]
    
    # Verificar que existe el directorio origen
    if not os.path.exists(SOURCE_DIR):
        print(f"Error: El directorio origen no existe: {SOURCE_DIR}")
        sys.exit(1)
    
    # Por defecto COPIA los archivos (no los mueve) para mayor seguridad
    # Si quieres moverlos en lugar de copiarlos, cambia copy_files=False
    consolidate_photos(SOURCE_DIR, DESTINATION_DIR, copy_files=True)
