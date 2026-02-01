import argparse
import glob
import os
import pathlib
import re
from datetime import datetime
from typing import Set, Dict, Tuple, Optional
from PIL import Image
from PIL.ExifTags import TAGS

import win32utils
from win32utils import CopyParams

# Extensiones de archivos multimedia soportadas
MULTIMEDIA_EXTENSIONS: Set[str] = {
    # Imágenes
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.heic', '.heif', '.raw', '.cr2', '.nef', '.arw', '.dng',
    '.webp', '.ico',
    # Videos
    '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.wmv',
    '.flv', '.webm', '.mpeg', '.mpg'
}

# Meses en catalán
MESOS_CATALA = {
    1: "01-Gener",
    2: "02-Febrer",
    3: "03-Març",
    4: "04-Abril",
    5: "05-Maig",
    6: "06-Juny",
    7: "07-Juliol",
    8: "08-Agost",
    9: "09-Setembre",
    10: "10-Octubre",
    11: "11-Novembre",
    12: "12-Desembre"
}

def is_multimedia_file(filename: str) -> bool:
    """Verifica si un archivo es multimedia basándose en su extensión."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in MULTIMEDIA_EXTENSIONS


def get_file_date_from_exif(shell_item) -> Optional[datetime]:
    """
    Intenta extraer la fecha de un archivo de imagen desde los metadatos EXIF.
    Retorna None si no se puede obtener la fecha.
    """
    try:
        # Intentar obtener la ruta local del archivo
        try:
            file_path = shell_item.GetDisplayName(0x80058000)  # SIGDN_FILESYSPATH
            if os.path.exists(file_path):
                with Image.open(file_path) as img:
                    exif_data = img._getexif()
                    if exif_data:
                        for tag_id, value in exif_data.items():
                            tag = TAGS.get(tag_id, tag_id)
                            if tag == "DateTimeOriginal" or tag == "DateTime":
                                # Formato: "2025:01:15 14:30:45"
                                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
        except:
            pass
    except:
        pass
    return None


def get_file_date_from_name(filename: str) -> Optional[datetime]:
    """
    Intenta extraer la fecha del nombre del archivo.
    Soporta formatos como: IMG_20250115_143045.jpg, 202501_a\IMG_1694.HEIC, etc.
    """
    try:
        # Patrón para fechas en formato YYYYMMDD
        match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
        if match:
            year, month, day = match.groups()
            return datetime(int(year), int(month), int(day))
        
        # Patrón para carpetas YYYYMM
        match = re.search(r'(\d{6})_?[a-z]?', filename)
        if match:
            year_month = match.group(1)
            year = int(year_month[:4])
            month = int(year_month[4:6])
            return datetime(year, month, 1)
    except:
        pass
    return None


def get_file_date(shell_item, filename: str) -> datetime:
    """
    Obtiene la fecha de un archivo multimedia.
    Prioridad: 1) EXIF, 2) Nombre del archivo, 3) Fecha actual
    """
    # Intentar obtener fecha de EXIF
    date = get_file_date_from_exif(shell_item)
    if date:
        return date
    
    # Intentar obtener fecha del nombre
    date = get_file_date_from_name(filename)
    if date:
        return date
    
    # Por defecto, usar fecha actual
    return datetime.now()


def get_organized_path(filename: str, shell_item, base_year: Optional[int] = None) -> str:
    """
    Genera la ruta organizada para un archivo: YYYY/MM-MesEnCatala/filename
    """
    file_date = get_file_date(shell_item, filename)
    
    # Si se especifica un año base, usarlo (útil para mantener consistencia)
    year = base_year if base_year else file_date.year
    month_folder = MESOS_CATALA[file_date.month]
    
    return os.path.join(str(year), month_folder, os.path.basename(filename))


# changes "a" to "_" in "202301_a\IMG_1694.HEIC"
def remove_letter_suffix_from_folder(filePath):
    return re.sub("_[a-z]\\\\", "__\\\\", filePath)


# Loads paths of already imported files into a set
def load_already_imported_file_names(metadata_folder):
    already_imported_files_set = set()
    if metadata_folder is not None:
        if not os.path.exists(metadata_folder):
            raise Exception(f"{metadata_folder} does not exist")
        if not os.path.isdir(metadata_folder):
            raise Exception(f"{metadata_folder} is not a folder")
        else:
            for filename in glob.glob(os.path.join(metadata_folder, "*.txt")):
                print(f"Loading imported file list from '{filename}'")
                with open(filename, "r") as file:
                    for line in file:
                        filename = line.strip()
                        amendedFilename = remove_letter_suffix_from_folder(filename)
                        already_imported_files_set.add(amendedFilename)
    print(f"Loaded {len(already_imported_files_set)} imported files")
    return already_imported_files_set


# Resolves which files to import
def resolve_items_to_import(source_folder_absolute_display_name, source_shell_items_by_path,
                            already_imported_files_set, organize_by_date=True):
    imported_file_set = set()
    not_imported_file_set = set()
    shell_items_to_copy = {}
    skipped_non_multimedia = 0
    
    for path in sorted(source_shell_items_by_path.keys()):
        source_file_shell_item = source_shell_items_by_path[path]
        source_file_absolute_path = win32utils.get_absolute_name(source_file_shell_item)
        file_relative_path = remove_prefix(source_file_absolute_path, source_folder_absolute_display_name)
        file_relative_path = remove_prefix(file_relative_path, '\\')
        
        # Verificar si es un archivo multimedia
        if not is_multimedia_file(file_relative_path):
            skipped_non_multimedia += 1
            continue
        
        amended_file_path = remove_letter_suffix_from_folder(file_relative_path)
        
        if amended_file_path not in already_imported_files_set:
            # Si se organiza por fecha, generar nueva ruta
            if organize_by_date:
                try:
                    organized_path = get_organized_path(file_relative_path, source_file_shell_item)
                    shell_items_to_copy[organized_path] = source_file_shell_item
                    imported_file_set.add(organized_path)
                except Exception as e:
                    print(f"Error organizando {file_relative_path}: {e}. Usando ruta original.")
                    shell_items_to_copy[file_relative_path] = source_file_shell_item
                    imported_file_set.add(amended_file_path)
            else:
                shell_items_to_copy[file_relative_path] = source_file_shell_item
                imported_file_set.add(amended_file_path)
        else:
            not_imported_file_set.add(file_relative_path)
    
    if skipped_non_multimedia > 0:
        print(f"Omitidos {skipped_non_multimedia} archivos no multimedia")
    
    return imported_file_set, not_imported_file_set, shell_items_to_copy


def remove_prefix(str, prefix):
    if not str.startswith(prefix):
        raise Exception(f"'{str}' should start with '{prefix}")
    return str[len(prefix):]


def copy_using_windows_shell(shell_items_to_copy_by_target_path, destination_base_path_str):
    target_folder_shell_item_by_path = {}
    copy_params_list = []
    created_folders = set()
    
    for destination_file_path in sorted(shell_items_to_copy_by_target_path.keys()):
        try:
            desination_full_path = os.path.join(destination_base_path_str, destination_file_path)
            desination_folder = os.path.dirname(desination_full_path)
            desination_filename = os.path.basename(desination_full_path)
            
            # Crear carpetas de destino si no existen
            if desination_folder not in target_folder_shell_item_by_path:
                if desination_folder not in created_folders:
                    try:
                        pathlib.Path(desination_folder).mkdir(parents=True, exist_ok=True)
                        created_folders.add(desination_folder)
                    except Exception as e:
                        print(f"Error creando carpeta {desination_folder}: {e}")
                        continue
                
                try:
                    target_folder_shell_item = win32utils.get_shell_item_from_path(desination_folder)
                    target_folder_shell_item_by_path[desination_folder] = target_folder_shell_item
                except Exception as e:
                    print(f"Error obteniendo shell item para {desination_folder}: {e}")
                    continue
            
            # Verificar si el archivo ya existe y generar nombre único si es necesario
            final_filename = desination_filename
            counter = 1
            while os.path.exists(os.path.join(desination_folder, final_filename)):
                name, ext = os.path.splitext(desination_filename)
                final_filename = f"{name}_{counter}{ext}"
                counter += 1
            
            source_file_shell_item = shell_items_to_copy_by_target_path[destination_file_path]
            copy_params = CopyParams(source_file_shell_item, target_folder_shell_item_by_path[desination_folder],
                                     final_filename)
            copy_params_list.append(copy_params)
        except Exception as e:
            print(f"Error preparando copia de {destination_file_path}: {e}")
            continue
    
    if copy_params_list:
        try:
            win32utils.copy_multiple_files(copy_params_list)
        except Exception as e:
            print(f"Error durante la copia de archivos: {e}")
            print("Intentando copiar archivos uno por uno...")
            # Fallback: copiar uno por uno si falla la copia masiva
            for copy_param in copy_params_list:
                try:
                    win32utils.copy_single_file(
                        copy_param.sourcefile_shell_item,
                        copy_param.destinationFolder_shell_item,
                        copy_param.target_filename
                    )
                except Exception as e2:
                    src_name = win32utils.get_absolute_name(copy_param.sourcefile_shell_item)
                    print(f"Error copiando {src_name}: {e2}")


def write_imported_file_list_to_metadata_folder(metadata_folder, file_path_set):
    time_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    imported_files_metadata_path = os.path.join(metadata_folder, f"imported_{time_str}.txt")
    print(f"Writing '{imported_files_metadata_path}'")
    with open(imported_files_metadata_path, "w") as file:
        for filename in sorted(list(file_path_set)):
            file.write(f"{filename}\n")


def main(args):
    print(f"=== iPhone Import - Organización automática por meses ===")
    print(f"Origen: {args.source}")
    print(f"Destino: {args.destination}")
    print(f"Organizar por fecha: {'Sí' if not args.no_organize else 'No'}")
    print("=" * 60)

    source_folder_absolute_display_name = args.source
    destination_path_str = args.destination

    try:
        already_imported_files_set = load_already_imported_file_names(args.metadata_folder)
    except Exception as e:
        print(f"Error cargando archivos importados: {e}")
        already_imported_files_set = set()

    try:
        source_folder_shell_folder = win32utils.get_shell_folder_from_absolute_display_name(
            source_folder_absolute_display_name)
    except Exception as e:
        print(f"ERROR: No se puede acceder a la carpeta de origen: {e}")
        print("Verifica que el iPhone esté conectado y que la ruta sea correcta.")
        return

    try:
        print("\nEscaneando archivos del iPhone...")
        source_shell_items_by_path = win32utils.walk_dcim(source_folder_shell_folder)
        print(f"Total de archivos encontrados: {len(source_shell_items_by_path)}")
    except Exception as e:
        print(f"ERROR: Error escaneando archivos: {e}")
        return

    try:
        organize_by_date = not args.no_organize
        imported_file_set, not_imported_file_set, shell_items_to_copy_by_target_path = resolve_items_to_import(
            source_folder_absolute_display_name, source_shell_items_by_path, already_imported_files_set, organize_by_date)
    except Exception as e:
        print(f"ERROR: Error resolviendo archivos a importar: {e}")
        return

    print(f"\nArchivos multimedia a importar: {len(imported_file_set)}")
    print(f"Archivos ya importados (omitidos): {len(not_imported_file_set)}")

    if args.skip_copy:
        print(f"\nModo skip-copy activado, omitiendo copia de archivos")
    elif len(shell_items_to_copy_by_target_path) > 0:
        print(f"\nIniciando copia de {len(shell_items_to_copy_by_target_path)} archivos...")
        try:
            copy_using_windows_shell(shell_items_to_copy_by_target_path, destination_path_str)
            print("\n✓ Copia completada exitosamente!")
        except Exception as e:
            print(f"\nERROR durante la copia: {e}")
            print("Algunos archivos pueden no haberse copiado correctamente.")
    else:
        print(f"\nNo hay archivos nuevos para copiar")

    if len(imported_file_set) > 0 and args.metadata_folder:
        try:
            write_imported_file_list_to_metadata_folder(args.metadata_folder, imported_file_set)
        except Exception as e:
            print(f"Advertencia: Error guardando metadatos: {e}")
    
    print("\n" + "=" * 60)
    print("Proceso finalizado")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Importa y organiza fotos y videos del iPhone por año y mes en catalán",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python __main__.py "Este equipo\\Apple iPhone\\Internal Storage" "D:\\iPhone\\2025"
  python __main__.py "Este equipo\\Apple iPhone\\Internal Storage" "D:\\Fotos" --metadata-folder "D:\\metadata"
  python __main__.py "Este equipo\\Apple iPhone\\Internal Storage" "D:\\Fotos" --no-organize
        """
    )
    parser.add_argument('source', help='Ruta de origen (ej: "Este equipo\\Apple iPhone\\Internal Storage")')
    parser.add_argument('destination', help='Carpeta de destino donde se copiarán las fotos')
    parser.add_argument('--metadata-folder', required=False, 
                       help='Carpeta para guardar metadatos de archivos ya importados')
    parser.add_argument('--skip-copy', required=False, action='store_true',
                       help='Solo simular, no copiar archivos realmente')
    parser.add_argument('--no-organize', required=False, action='store_true',
                       help='No organizar por fecha, mantener estructura original')
    
    try:
        main(parser.parse_args())
    except KeyboardInterrupt:
        print("\n\nProceso interrumpido por el usuario")
    except Exception as e:
        print(f"\nERROR FATAL: {e}")
        import traceback
        traceback.print_exc()
