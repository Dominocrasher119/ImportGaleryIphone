"""
Shell-based device access for iPhone media scanning.
Uses Windows Shell API (IShellFolder/IShellItem) which has better iPhone support than WPD.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import pythoncom
from win32comext.shell import shell, shellcon

from domain import CancelToken, DeviceInfo, MediaItem, PHOTO_EXTS, VIDEO_EXTS
from domain.errors import ScanCancelled, ScanError
from infrastructure.fs.path_utils import ensure_cache_dir


def _make_scan_logger():
    """Create a simple file logger under _cache/scan_logs for troubleshooting scans."""
    cache_dir = ensure_cache_dir() / 'scan_logs'
    cache_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('scan_%Y%m%d_%H%M%S.log')
    log_path = cache_dir / ts

    def _log(msg: str) -> None:
        line = f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
        try:
            with log_path.open('a', encoding='utf-8') as handle:
                handle.write(line + '\n')
        except Exception:
            pass

    return _log, log_path


def _get_desktop_shell_folder():
    """Get the desktop shell folder (root of shell namespace)."""
    return shell.SHGetDesktopFolder()


def _get_child_shell_folder(parent_shell_folder, child_name: str):
    """Get a child shell folder by display name."""
    for child_pidl in parent_shell_folder:
        try:
            display_name = parent_shell_folder.GetDisplayNameOf(child_pidl, shellcon.SHGDN_NORMAL)
            if display_name.lower() == child_name.lower():
                return parent_shell_folder.BindToObject(child_pidl, None, shell.IID_IShellFolder)
        except Exception:
            continue
    return None


def _find_iphone_storage(log=None) -> tuple:
    """
    Find the iPhone's Internal Storage shell folder.
    Returns (shell_folder, display_path) or (None, None) if not found.
    """
    desktop = _get_desktop_shell_folder()
    
    # Common names for "This PC" in different languages
    this_pc_names = ['This PC', 'Este equipo', 'Aquest equip', 'Dieser PC', 'Ce PC']
    
    this_pc = None
    for name in this_pc_names:
        this_pc = _get_child_shell_folder(desktop, name)
        if this_pc:
            if log:
                log(f'Found "This PC" as "{name}"')
            break
    
    if not this_pc:
        if log:
            log('Could not find "This PC"')
        return None, None
    
    # Find iPhone
    iphone_folder = None
    iphone_name = None
    for pidl in this_pc:
        try:
            name = this_pc.GetDisplayNameOf(pidl, shellcon.SHGDN_NORMAL)
            if 'iphone' in name.lower() or 'apple' in name.lower():
                iphone_folder = this_pc.BindToObject(pidl, None, shell.IID_IShellFolder)
                iphone_name = name
                if log:
                    log(f'Found iPhone: "{name}"')
                break
        except Exception:
            continue
    
    if not iphone_folder:
        if log:
            log('Could not find iPhone in This PC')
        return None, None
    
    # Find Internal Storage
    storage_names = ['Internal Storage', 'Almacenamiento interno', 'Emmagatzematge intern']
    storage_folder = None
    storage_name = None
    
    for pidl in iphone_folder:
        try:
            name = iphone_folder.GetDisplayNameOf(pidl, shellcon.SHGDN_NORMAL)
            if log:
                log(f'  iPhone child: "{name}"')
            for pattern in storage_names:
                if pattern.lower() in name.lower():
                    storage_folder = iphone_folder.BindToObject(pidl, None, shell.IID_IShellFolder)
                    storage_name = name
                    break
            if storage_folder:
                break
        except Exception:
            continue
    
    if storage_folder:
        display_path = f'{iphone_name}\\{storage_name}'
        if log:
            log(f'Using storage: "{display_path}"')
        return storage_folder, display_path
    
    if log:
        log('Could not find Internal Storage')
    return None, None


def _walk_shell_folder(shell_folder, path: str, items: list, log, cancel_token, progress_cb, 
                       items_cb, depth: int = 0, stats: dict = None, pending_items: list = None):
    """
    Recursively walk a shell folder and collect media items.
    Emits items in batches for real-time UI updates.
    """
    if depth > 16:
        return
    
    if cancel_token and cancel_token.cancelled:
        raise ScanCancelled()
    
    if stats is None:
        stats = {'folders': 0, 'files': 0, 'media': 0}
    
    if pending_items is None:
        pending_items = []
    
    stats['folders'] += 1
    
    # Report progress with current folder
    if progress_cb:
        progress_cb(stats['media'], stats['folders'], path)
    
    # Enumerate folders first
    try:
        for folder_pidl in shell_folder.EnumObjects(0, shellcon.SHCONTF_FOLDERS):
            if cancel_token and cancel_token.cancelled:
                raise ScanCancelled()
            try:
                child_folder = shell_folder.BindToObject(folder_pidl, None, shell.IID_IShellFolder)
                folder_name = shell_folder.GetDisplayNameOf(folder_pidl, shellcon.SHGDN_NORMAL)
                child_path = f'{path}\\{folder_name}' if path else folder_name
                
                if stats['folders'] <= 20:
                    log(f'📁 {child_path}')
                
                _walk_shell_folder(child_folder, child_path, items, log, cancel_token, 
                                   progress_cb, items_cb, depth + 1, stats, pending_items)
            except Exception as e:
                log(f'Error accessing folder: {e}')
                continue
    except Exception as e:
        log(f'Error enumerating folders in {path}: {e}')
    
    # Enumerate files
    try:
        folder_new_items = []
        for file_pidl in shell_folder.EnumObjects(0, shellcon.SHCONTF_NONFOLDERS):
            if cancel_token and cancel_token.cancelled:
                raise ScanCancelled()
            try:
                stats['files'] += 1
                
                # Get file info
                file_name = shell_folder.GetDisplayNameOf(file_pidl, shellcon.SHGDN_NORMAL)
                extension = Path(file_name).suffix.lower()
                
                # Check if media
                if extension not in PHOTO_EXTS and extension not in VIDEO_EXTS:
                    continue
                
                stats['media'] += 1
                
                # Get shell item for more info
                try:
                    folder_pidl_abs = shell.SHGetIDListFromObject(shell_folder)
                    shell_item = shell.SHCreateShellItem(folder_pidl_abs, None, file_pidl)
                    abs_path = shell_item.GetDisplayName(shellcon.SIGDN_DESKTOPABSOLUTEEDITING)
                except Exception:
                    abs_path = f'{path}\\{file_name}'
                    shell_item = None
                
                # Try to get size (from shell item attributes if available)
                size = 0
                created = None
                
                # Create MediaItem
                item = MediaItem(
                    device_id='shell',  # Will be updated by caller
                    object_id=abs_path,  # Use absolute path as object_id
                    name=file_name,
                    extension=extension,
                    size=size,
                    created=created,
                    device_path=f'{path}\\{file_name}' if path else file_name,
                    content_type='',
                )
                items.append(item)
                folder_new_items.append(item)
                
                if stats['media'] <= 20:
                    log(f'  📷 {file_name}')
                    
            except Exception as e:
                log(f'Error processing file: {e}')
                continue
        
        # Emit batch of items found in this folder for real-time UI updates
        if folder_new_items and items_cb:
            items_cb(folder_new_items)
            
    except Exception as e:
        log(f'Error enumerating files in {path}: {e}')


ProgressCb = Optional[Callable[[int, int, str], None]]
ItemsCb = Optional[Callable[[list], None]]


def list_media_items_shell(
    device_id: str,
    progress_cb: ProgressCb = None,
    items_cb: ItemsCb = None,
    cancel_token: CancelToken | None = None,
) -> list[MediaItem]:
    """
    List media items from iPhone using Windows Shell API.
    This is more reliable than WPD for iPhones.
    Emits items in real-time via items_cb for UI responsiveness.
    """
    log, log_path = _make_scan_logger()
    items: list[MediaItem] = []
    
    log(f'Start shell scan device_id={device_id}')
    
    pythoncom.CoInitialize()
    try:
        # Find iPhone storage
        storage_folder, storage_path = _find_iphone_storage(log)
        
        if not storage_folder:
            log('ERROR: Could not find iPhone storage')
            raise ScanError('error_device_not_found', detail='Could not find iPhone Internal Storage')
        
        log(f'Starting walk of {storage_path}')
        stats = {'folders': 0, 'files': 0, 'media': 0}
        
        # Wrap items_cb to update device_id before emitting
        def items_cb_wrapper(new_items):
            for item in new_items:
                item.device_id = device_id
            if items_cb:
                items_cb(new_items)
        
        _walk_shell_folder(storage_folder, storage_path, items, log, cancel_token, 
                           progress_cb, items_cb_wrapper, depth=0, stats=stats)
        
        # Update device_id in all items (for items added before wrapper was set)
        for item in items:
            item.device_id = device_id
        
        log(f'Finished scan. folders={stats["folders"]} files={stats["files"]} media={stats["media"]}')
        
    except ScanCancelled:
        log('Scan cancelled by user')
        raise
    except ScanError:
        raise
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        log(f'ERROR: {exc}')
        log(tb)
        raise ScanError('error_scan_failed', detail=str(log_path)) from exc
    finally:
        pythoncom.CoUninitialize()
    
    return items


def download_file_shell(
    object_id: str,  # This is the absolute shell path
    dest_path: Path,
    progress_cb,
    cancel_token,
) -> bool:
    """
    Download a file from iPhone using Windows Shell API.
    object_id is the absolute shell path (e.g., "This PC\Apple iPhone\Internal Storage\DCIM\...")
    """
    pythoncom.CoInitialize()
    try:
        # Create destination folder
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get source shell item
        source_item = shell.SHCreateItemFromParsingName(object_id, None, shell.IID_IShellItem)
        
        # Get destination folder shell item
        dest_folder = shell.SHCreateItemFromParsingName(str(dest_path.parent), None, shell.IID_IShellItem)
        
        # Create file operation
        pfo = pythoncom.CoCreateInstance(
            shell.CLSID_FileOperation,
            None,
            pythoncom.CLSCTX_ALL,
            shell.IID_IFileOperation
        )
        
        # Set flags for silent operation
        pfo.SetOperationFlags(
            shellcon.FOF_NO_UI |
            shellcon.FOF_NOCONFIRMATION |
            shellcon.FOF_SILENT
        )
        
        # Queue copy operation
        pfo.CopyItem(source_item, dest_folder, dest_path.name, None)
        
        # Execute
        pfo.PerformOperations()
        
        return dest_path.exists()
        
    except Exception as e:
        print(f'Shell download error: {e}')
        return False
    finally:
        pythoncom.CoUninitialize()
