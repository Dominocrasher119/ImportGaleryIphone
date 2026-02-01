from dataclasses import dataclass

import pythoncom
from win32comext.shell import shell, shellcon


@dataclass
class CopyParams:
    sourcefile_shell_item: object
    destinationFolder_shell_item: object
    target_filename: str


def get_desktop_shell_folder():
    return shell.SHGetDesktopFolder()


# returns the child shell folder of a shell folder with a given name
def get_child_shell_folder_with_display_name(parent_shell_folder, child_folder_name: str):
    for child_pidl in parent_shell_folder:
        child_display_name = parent_shell_folder.GetDisplayNameOf(child_pidl, shellcon.SHGDN_NORMAL)
        if child_display_name == child_folder_name:
            return parent_shell_folder.BindToObject(child_pidl, None, shell.IID_IShellFolder)
    raise Exception(f"Cannot find {child_folder_name}")


# returns a shell folder for a string path, e.g. "This PC\Apple iPhone\Internal Storage\DCIM"
def get_shell_folder_from_absolute_display_name(display_names):
    current_shell_folder = get_desktop_shell_folder()
    folders = display_names.split("\\")
    for folder in folders:
        try:
            current_shell_folder = get_child_shell_folder_with_display_name(current_shell_folder, folder)
        except BaseException as exception:
            raise Exception(f"Cannot get shell folder for {display_names} (at '{folder}')") from exception
    return current_shell_folder


# returns a shell item for a string path, e.g. "This PC\Apple iPhone\Internal Storage\DCIM\IMG_0091.JPG"
def get_shell_item_from_path(path):
    try:
        return shell.SHCreateItemFromParsingName(path, None, shell.IID_IShellItem)
    except BaseException as exception:
        raise Exception(f"Cannot get shell item for {path}") from exception


# returns a dictionary of (file name -> shell item) of files in shell folder
def walk_dcim(shell_folder):
    """
    Recorre recursivamente las carpetas del dispositivo y retorna todos los archivos.
    Maneja errores de forma robusta para evitar que falle toda la operación.
    """
    result = {}

    try:
        # Enumerar carpetas
        for folder_pidl in shell_folder.EnumObjects(0, shellcon.SHCONTF_FOLDERS):
            try:
                child_shell_folder = shell_folder.BindToObject(folder_pidl, None, shell.IID_IShellFolder)
                name = shell_folder.GetDisplayNameOf(folder_pidl, shellcon.SHGDN_FORADDRESSBAR)
                print(f"📁 Explorando carpeta: '{name}'")
                # Recursión para subcarpetas
                result |= walk_dcim(child_shell_folder)
            except Exception as e:
                print(f"  Advertencia: Error accediendo a subcarpeta: {e}")
                continue
    except Exception as e:
        print(f"  Advertencia: Error enumerando carpetas: {e}")

    try:
        # Enumerar archivos
        file_count = 0
        for file_pidl in shell_folder.EnumObjects(0, shellcon.SHCONTF_NONFOLDERS):
            try:
                sourcefolder_pidl = shell.SHGetIDListFromObject(shell_folder)
                sourcefile_shell_item = shell.SHCreateShellItem(sourcefolder_pidl, None, file_pidl)
                sourcefile_name = get_absolute_name(sourcefile_shell_item)
                result[sourcefile_name] = sourcefile_shell_item
                file_count += 1
            except Exception as e:
                print(f"  Advertencia: Error procesando un archivo: {e}")
                continue
        
        if file_count > 0:
            print(f"  ✓ {file_count} archivos encontrados")
    except Exception as e:
        print(f"  Advertencia: Error enumerando archivos: {e}")

    return result


def copy_single_file(sourcefile_shell_item, destination_folder_shell_item, target_filename):
    """Copia un solo archivo usando la API de Windows Shell."""
    try:
        src_name = get_absolute_name(sourcefile_shell_item)
        dst_name = get_absolute_name(destination_folder_shell_item)
        print(f"Copiando '{src_name}' a '{dst_name}\\{target_filename}'")

        pfo = pythoncom.CoCreateInstance(shell.CLSID_FileOperation,
                                        None,
                                        pythoncom.CLSCTX_ALL,
                                        shell.IID_IFileOperation)
        
        # Configurar flags para evitar diálogos y manejar conflictos automáticamente
        pfo.SetOperationFlags(
            shellcon.FOF_NO_UI |  # Sin UI
            shellcon.FOF_NOCONFIRMATION |  # Sin confirmación
            shellcon.FOF_SILENT  # Silencioso
        )
        
        pfo.CopyItem(sourcefile_shell_item, destination_folder_shell_item, target_filename, None)
        pfo.PerformOperations()
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def copy_multiple_files(copy_params_list: list[CopyParams]):
    """Copia múltiples archivos en una sola operación usando la API de Windows Shell."""
    if not copy_params_list:
        print("No hay archivos para copiar")
        return
    
    try:
        fileOperationObject = pythoncom.CoCreateInstance(shell.CLSID_FileOperation,
                                                        None,
                                                        pythoncom.CLSCTX_ALL,
                                                        shell.IID_IFileOperation)
        
        # Configurar flags para evitar diálogos y manejar conflictos automáticamente
        fileOperationObject.SetOperationFlags(
            shellcon.FOF_NO_UI |  # Sin UI
            shellcon.FOF_NOCONFIRMATION |  # Sin confirmación
            shellcon.FOF_SILENT  # Silencioso
        )
        
        print(f"\nPreparando {len(copy_params_list)} archivos para copiar...")
        for i, copy_params in enumerate(copy_params_list, 1):
            try:
                src_str = get_absolute_name(copy_params.sourcefile_shell_item)
                dst_str = get_absolute_name(copy_params.destinationFolder_shell_item)
                if i <= 5 or i % 50 == 0:  # Mostrar solo los primeros 5 y cada 50
                    print(f"  [{i}/{len(copy_params_list)}] {os.path.basename(src_str)}")
                fileOperationObject.CopyItem(copy_params.sourcefile_shell_item, 
                                           copy_params.destinationFolder_shell_item,
                                           copy_params.target_filename,
                                           None)
            except Exception as e:
                print(f"  Error preparando archivo {i}: {e}")
        
        print(f"\nEjecutando operación de copia de {len(copy_params_list)} archivos...")
        fileOperationObject.PerformOperations()
        print("✓ Operación de copia completada")
    except Exception as e:
        print(f"ERROR en copia masiva: {e}")
        raise


def get_absolute_name(shell_item):
    return shell_item.GetDisplayName(shellcon.SIGDN_DESKTOPABSOLUTEEDITING)


def get_diplay_name(shell_item):
    return shell_item.GetDisplayName(shellcon.SIGDN_NORMALDISPLAY)
