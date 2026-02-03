from __future__ import annotations

import ctypes
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional
import traceback

import comtypes
import comtypes.client
from comtypes import COMError, GUID

from domain import CancelToken, DeviceInfo, MediaItem, PHOTO_EXTS, VIDEO_EXTS
from domain.errors import ScanCancelled, ScanError
from infrastructure.fs.path_utils import ensure_cache_dir

WPD_DEVICE_OBJECT_ID = 'DEVICE'
STGM_READ = 0x00000000

# Content type GUIDs for containers
WPD_CONTENT_TYPE_FOLDER = GUID("{27E2E392-A111-48E0-AB0C-E17705A05F85}")
# Functional objects are used for storage roots on some devices (e.g., iPhone)
WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT = GUID("{99ED0160-17FF-4008-8A21-7F9C1B91036B}")
CONTAINER_CONTENT_TYPES = {WPD_CONTENT_TYPE_FOLDER, WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT}

# Content type GUIDs for media detection (fallback when extension is missing)
WPD_CONTENT_TYPE_IMAGE = GUID("{EF2107D5-A52A-4243-A26B-62D4176D7603}")
WPD_CONTENT_TYPE_VIDEO = GUID("{9261B03C-3D78-4519-85E3-02C5E1F50BB9}")
WPD_CONTENT_TYPE_AUDIO = GUID("{4AD2C85E-5E2D-45E5-8864-4F229E3C6CF0}")
MEDIA_CONTENT_TYPES = {WPD_CONTENT_TYPE_IMAGE, WPD_CONTENT_TYPE_VIDEO}

# Internal storage name patterns (multilingual)
INTERNAL_STORAGE_PATTERNS = (
    'internal storage',
    'almacenamiento interno',
    'emmagatzematge intern',
)

# Cache for WPD property keys
_wpd_keys_cache = {}


def _make_property_key(Types, fmtid_str: str, pid: int):
    """Create a PROPERTYKEY using the Types module's _tagpropertykey."""
    pk = Types._tagpropertykey()
    pk.fmtid = GUID(fmtid_str)
    pk.pid = pid
    return pk


def _get_wpd_keys(Types):
    """Get or create cached WPD property keys."""
    global _wpd_keys_cache
    if _wpd_keys_cache:
        return _wpd_keys_cache
    
    _wpd_keys_cache = {
        'CLIENT_NAME': _make_property_key(Types, "{204D9F0C-2292-4080-9F42-40664E70F859}", 2),
        'CLIENT_MAJOR_VERSION': _make_property_key(Types, "{204D9F0C-2292-4080-9F42-40664E70F859}", 3),
        'CLIENT_MINOR_VERSION': _make_property_key(Types, "{204D9F0C-2292-4080-9F42-40664E70F859}", 4),
        'CLIENT_REVISION': _make_property_key(Types, "{204D9F0C-2292-4080-9F42-40664E70F859}", 5),
        'OBJECT_NAME': _make_property_key(Types, "{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}", 4),
        'OBJECT_ORIGINAL_FILE_NAME': _make_property_key(Types, "{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}", 12),
        'OBJECT_SIZE': _make_property_key(Types, "{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}", 11),
        'OBJECT_CONTENT_TYPE': _make_property_key(Types, "{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}", 7),
        'OBJECT_DATE_CREATED': _make_property_key(Types, "{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}", 18),
        'OBJECT_DATE_MODIFIED': _make_property_key(Types, "{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}", 19),
        'RESOURCE_DEFAULT': _make_property_key(Types, "{E81E79BE-34F0-41BF-B53F-F1A06AE87842}", 0),
    }
    return _wpd_keys_cache


def _setup_comtypes_cache() -> None:
    cache_dir = ensure_cache_dir() / 'comtypes_gen'
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        import os
        os.environ['COMTYPES_GEN_PATH'] = str(cache_dir)
    except Exception:
        pass
    comtypes.client.gen_dir = str(cache_dir)


def _ensure_wpd_module():
    _setup_comtypes_cache()
    comtypes.client.GetModule('portabledeviceapi.dll')
    comtypes.client.GetModule('portabledevicetypes.dll')
    from comtypes.gen import PortableDeviceApiLib as API
    from comtypes.gen import PortableDeviceTypesLib as Types
    return API, Types


def _get_wpd_api():
    """Get only the API module for backwards compatibility."""
    api, _ = _ensure_wpd_module()
    return api


@contextmanager
def com_context():
    comtypes.CoInitialize()
    try:
        yield
    finally:
        comtypes.CoUninitialize()


def _get_device_string(mgr, device_id: str, method_name: str) -> str:
    method = getattr(mgr, method_name)
    length = ctypes.c_ulong(0)
    method(device_id, None, ctypes.byref(length))
    if length.value == 0:
        return ''
    buffer = ctypes.create_unicode_buffer(length.value)
    method(device_id, buffer, ctypes.byref(length))
    return buffer.value


def _get_device_string_direct(mgr, device_id: str, method_name: str) -> str:
    """Get device string using direct COM calls (bypasses broken comtypes wrapper)."""
    try:
        # Use the internal COM method directly
        com_method = getattr(mgr, f'_IPortableDeviceManager__com_{method_name}')
        length = ctypes.c_ulong(0)
        # First call to get required buffer length
        hr = com_method(device_id, None, ctypes.byref(length))
        if hr != 0 or length.value == 0:
            return ''
        # Second call to get the actual string - use c_ushort array (WCHAR*)
        buffer = (ctypes.c_ushort * length.value)()
        hr = com_method(device_id, buffer, ctypes.byref(length))
        if hr != 0:
            return ''
        # Convert ushort array to string
        return ''.join(chr(c) for c in buffer if c)
    except Exception:
        return ''


def list_devices() -> list[DeviceInfo]:
    """List all WPD devices using direct COM calls."""
    devices: list[DeviceInfo] = []
    with com_context():
        API, Types = _ensure_wpd_module()
        mgr = comtypes.client.CreateObject(API.PortableDeviceManager)
        
        # Refresh device list first
        try:
            mgr.RefreshDeviceList()
        except Exception:
            pass
        
        # Use direct COM call - the high-level wrapper is broken
        count = ctypes.c_ulong(0)
        hr = mgr._IPortableDeviceManager__com_GetDevices(None, ctypes.byref(count))
        if hr != 0 or count.value == 0:
            return []
        
        # Allocate buffer and get device IDs
        device_ids = (ctypes.c_wchar_p * count.value)()
        hr = mgr._IPortableDeviceManager__com_GetDevices(device_ids, ctypes.byref(count))
        if hr != 0:
            return []
        
        for dev_id in device_ids:
            if not dev_id:
                continue
            name = _get_device_string_direct(mgr, dev_id, 'GetDeviceFriendlyName')
            manufacturer = _get_device_string_direct(mgr, dev_id, 'GetDeviceManufacturer')
            description = _get_device_string_direct(mgr, dev_id, 'GetDeviceDescription')
            devices.append(
                DeviceInfo(
                    id=dev_id,
                    name=name or dev_id,
                    manufacturer=manufacturer,
                    description=description,
                )
            )
    return devices


def _create_device_client_info(Types):
    keys = _get_wpd_keys(Types)
    client_info = comtypes.client.CreateObject(Types.PortableDeviceValues)
    client_info.SetStringValue(keys['CLIENT_NAME'], 'iImport')
    client_info.SetUnsignedIntegerValue(keys['CLIENT_MAJOR_VERSION'], 1)
    client_info.SetUnsignedIntegerValue(keys['CLIENT_MINOR_VERSION'], 0)
    client_info.SetUnsignedIntegerValue(keys['CLIENT_REVISION'], 0)
    return client_info


def _open_device(device_id: str):
    API, Types = _ensure_wpd_module()
    try:
        device = comtypes.client.CreateObject(API.PortableDeviceFTM)
    except Exception:
        device = comtypes.client.CreateObject(API.PortableDevice)
    client_info = _create_device_client_info(Types)
    device.Open(device_id, client_info)
    return device, API, Types


def _enum_object_ids(enum) -> Iterator[str]:
    """Enumerate object IDs from a WPD enumerator."""
    def _split_next(result):
        ids = None
        fetched = 0
        if isinstance(result, (list, tuple)):
            if len(result) >= 2:
                first, second = result[0], result[1]
                if isinstance(first, (int, ctypes.c_ulong)) and not isinstance(second, (int, ctypes.c_ulong)):
                    fetched = int(first)
                    ids = second
                else:
                    ids = first
                    fetched = int(second) if isinstance(second, (int, ctypes.c_ulong)) else 0
            elif len(result) == 1:
                ids = result[0]
                fetched = 1 if ids else 0
        else:
            ids = result
            fetched = 1 if ids else 0
        return ids, fetched

    while True:
        # comtypes may return (ids, fetched) or (fetched, ids) depending on version
        try:
            ids, fetched = _split_next(enum.Next(1))
            if not fetched:
                break
            if isinstance(ids, (list, tuple)):
                for obj_id in ids:
                    if obj_id:
                        yield obj_id
            elif ids:
                yield ids
        except Exception:
            break


def _get_values(props, object_id: str, keys: Iterable, Types) -> object:
    key_collection = comtypes.client.CreateObject(Types.PortableDeviceKeyCollection)
    for key in keys:
        key_collection.Add(key)
    return props.GetValues(object_id, key_collection)


def _get_all_values(props, object_id: str):
    """Get ALL available properties for an object (pass None for keys)."""
    return props.GetValues(object_id, None)


def _extract_object_info_from_all(values, keys_dict, Types) -> dict:
    """
    Extract object info from all available properties.
    Returns dict with 'name', 'size', 'content_type', 'created', 'modified'.
    Tries multiple property keys to find the filename.
    """
    info = {'name': '', 'original_name': '', 'size': 0, 'content_type': None, 'created': None, 'modified': None}
    
    # Known WPD property format IDs and PIDs for names
    # WPD_OBJECT_NAME = {EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}, 4
    # WPD_OBJECT_ORIGINAL_FILE_NAME = {EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}, 12
    # WPD_OBJECT_HINT_LOCATION_DISPLAY_NAME = {EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}, 13
    # WPD_OBJECT_ID = {EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}, 2
    
    # Try standard keys first
    info['name'] = _safe_get_string(values, keys_dict['OBJECT_NAME'])
    info['original_name'] = _safe_get_string(values, keys_dict['OBJECT_ORIGINAL_FILE_NAME'])
    info['size'] = _safe_get_unsigned(values, keys_dict['OBJECT_SIZE'])
    info['content_type'] = _safe_get_guid(values, keys_dict['OBJECT_CONTENT_TYPE'])
    info['created'] = _safe_get_date(values, keys_dict['OBJECT_DATE_CREATED'])
    info['modified'] = _safe_get_date(values, keys_dict['OBJECT_DATE_MODIFIED'])
    
    # If no name found, try to iterate all properties to find ANY string that looks like a filename
    if not info['name'] and not info['original_name']:
        try:
            count = values.GetCount()
            for i in range(count):
                try:
                    key = Types._tagpropertykey()
                    values.GetAt(i, ctypes.byref(key), None)
                    # Try to get as string
                    try:
                        val = values.GetStringValue(ctypes.pointer(key))
                        if val and '.' in val and len(val) < 260:
                            # Looks like a filename
                            ext = Path(val).suffix.lower()
                            if ext:
                                info['name'] = val
                                break
                    except:
                        pass
                except:
                    pass
        except:
            pass
    
    return info


def _safe_get_string(values, key, fallback: str = '') -> str:
    try:
        return values.GetStringValue(ctypes.pointer(key))
    except Exception:
        return fallback


def _safe_get_unsigned(values, key, fallback: int = 0) -> int:
    try:
        return int(values.GetUnsignedIntegerValue(ctypes.pointer(key)))
    except Exception:
        try:
            return int(values.GetUnsignedLargeIntegerValue(ctypes.pointer(key)))
        except Exception:
            return fallback


def _safe_get_guid(values, key):
    try:
        return values.GetGuidValue(ctypes.pointer(key))
    except Exception:
        return None


def _safe_get_date(values, key) -> datetime | None:
    try:
        value = values.GetValue(ctypes.pointer(key))
    except Exception:
        try:
            value = values.GetStringValue(ctypes.pointer(key))
        except Exception:
            return None
    return _coerce_datetime(value)


def _coerce_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
    if isinstance(value, (int, float)):
        try:
            return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=int(value) / 10)
        except Exception:
            return None
    if hasattr(value, 'value') and isinstance(value.value, datetime):
        return value.value
    return None


def _is_container_object(content_type, name: str, extension: str | None = None) -> bool:
    """
    Determine if an object is a container (folder/storage).
    
    Priority:
    1. If content_type is a known container type (FOLDER, FUNCTIONAL_OBJECT): True
    2. If content_type is known but NOT a container type: False
    3. If content_type is None/unknown: fallback to extension heuristic (no ext => container)
    """
    if content_type in CONTAINER_CONTENT_TYPES:
        return True
    # If we have a known content_type that is NOT a container, it's a file
    if content_type is not None:
        return False
    # Fallback: no content_type available, use extension heuristic
    ext = extension if extension is not None else Path(name).suffix
    return not ext


def _join_path(base: str, name: str) -> str:
    """Join device paths without leading separators."""
    if not base:
        return name
    return f'{base}/{name}'


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


def _find_internal_storage_root(content, props, Types, log=None) -> tuple[str, str]:
    """
    Find the Internal Storage root object on an iPhone.
    
    Strategy:
    1. Enumerate direct children of DEVICE
    2. Find objects with content_type == WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT
    3. Prioritize by name matching INTERNAL_STORAGE_PATTERNS
    4. Fallback: use the first functional object that has children
    5. Last resort: if only ONE child of DEVICE exists and it has children, use it
    
    Returns:
        tuple[str, str]: (object_id, object_name) of the internal storage root,
                         or (WPD_DEVICE_OBJECT_ID, 'DEVICE') if not found.
    """
    keys_dict = _get_wpd_keys(Types)
    functional_objects: list[tuple[str, str]] = []  # (id, name)
    all_children: list[tuple[str, str, object]] = []  # (id, name, content_type)
    
    if log:
        log('Searching for Internal Storage root...')
    
    enum = content.EnumObjects(0, WPD_DEVICE_OBJECT_ID, None)
    for child_id in _enum_object_ids(enum):
        prop_keys = [keys_dict['OBJECT_NAME'], keys_dict['OBJECT_CONTENT_TYPE']]
        values = _get_values(props, child_id, prop_keys, Types)
        name = _safe_get_string(values, keys_dict['OBJECT_NAME'])
        content_type = _safe_get_guid(values, keys_dict['OBJECT_CONTENT_TYPE'])
        
        if log:
            log(f'  DEVICE child: id={child_id}, name="{name}", content_type={content_type}')
        
        all_children.append((child_id, name, content_type))
        if content_type == WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT:
            functional_objects.append((child_id, name))
    
    # Strategy 1: Try functional objects first
    if functional_objects:
        # Try to find by name pattern (case-insensitive)
        for obj_id, obj_name in functional_objects:
            name_lower = obj_name.lower()
            for pattern in INTERNAL_STORAGE_PATTERNS:
                if pattern in name_lower:
                    if log:
                        log(f'Found Internal Storage by name: id={obj_id}, name="{obj_name}"')
                    return obj_id, obj_name
        
        # Fallback: find the first functional object that has children
        for obj_id, obj_name in functional_objects:
            try:
                child_enum = content.EnumObjects(0, obj_id, None)
                has_children = False
                for _ in _enum_object_ids(child_enum):
                    has_children = True
                    break
                if has_children:
                    if log:
                        log(f'Using first functional object with children: id={obj_id}, name="{obj_name}"')
                    return obj_id, obj_name
            except Exception:
                continue
        
        # Use the first functional object anyway
        obj_id, obj_name = functional_objects[0]
        if log:
            log(f'Using first functional object as fallback: id={obj_id}, name="{obj_name}"')
        return obj_id, obj_name
    
    # Strategy 2: No functional objects found - check if there's a single child with children
    # This handles iPhones where WPD doesn't report content_type correctly
    if log:
        log(f'No functional objects found. Checking {len(all_children)} children of DEVICE...')
    
    for obj_id, obj_name, _ in all_children:
        try:
            child_enum = content.EnumObjects(0, obj_id, None)
            has_children = False
            for _ in _enum_object_ids(child_enum):
                has_children = True
                break
            if has_children:
                display_name = obj_name if obj_name else f'<unnamed:{obj_id}>'
                if log:
                    log(f'Using child with sub-children as storage root: id={obj_id}, name="{display_name}"')
                return obj_id, display_name
        except Exception as e:
            if log:
                log(f'  Error checking children of {obj_id}: {e}')
            continue
    
    if log:
        log('No suitable storage root found, using DEVICE as root')
    return WPD_DEVICE_OBJECT_ID, 'DEVICE'


def _find_dcim_ids(content, root_id: str, Types) -> list[str]:
    props = content.Properties()
    result: list[str] = []
    keys_dict = _get_wpd_keys(Types)
    visited: set[str] = set()

    def walk(parent_id: str, depth: int) -> None:
        if depth > 4:
            return
        if parent_id in visited:
            return
        visited.add(parent_id)
        enum = content.EnumObjects(0, parent_id, None)
        for child_id in _enum_object_ids(enum):
            prop_keys = [keys_dict['OBJECT_NAME'], keys_dict['OBJECT_CONTENT_TYPE']]
            values = _get_values(props, child_id, prop_keys, Types)
            name = _safe_get_string(values, keys_dict['OBJECT_NAME'])
            content_type = _safe_get_guid(values, keys_dict['OBJECT_CONTENT_TYPE'])
            if name.upper() == 'DCIM':
                result.append(child_id)
            if _is_container_object(content_type, name):
                walk(child_id, depth + 1)

    walk(root_id, 0)
    return result


ProgressCb = Optional[Callable[[int, int, str], None]]


def _check_cancel(cancel_token: CancelToken | None) -> None:
    if cancel_token and cancel_token.cancelled:
        raise ScanCancelled()


ItemsCb = Optional[Callable[[list], None]]


def list_media_items(
    device_id: str,
    progress_cb: ProgressCb = None,
    items_cb: ItemsCb = None,
    cancel_token: CancelToken | None = None,
) -> list[MediaItem]:
    """
    List media items from a device.
    Tries Windows Shell API first (better iPhone support), falls back to WPD.
    """
    # Try Shell API first - it works much better with iPhones
    try:
        from infrastructure.wpd.shell_wrapper import list_media_items_shell
        items = list_media_items_shell(device_id, progress_cb, items_cb, cancel_token)
        if items:
            return items
    except ImportError:
        pass  # Shell wrapper not available
    except ScanCancelled:
        raise
    except Exception as e:
        # Shell API failed, try WPD
        log_shell, _ = _make_scan_logger()
        log_shell(f'Shell API failed, falling back to WPD: {e}')
    
    # Fallback to WPD (doesn't support items_cb)
    return _list_media_items_wpd(device_id, progress_cb, cancel_token)


def _list_media_items_wpd(
    device_id: str,
    progress_cb: ProgressCb = None,
    cancel_token: CancelToken | None = None,
) -> list[MediaItem]:
    """WPD-based media scanning (fallback)."""
    log, log_path = _make_scan_logger()
    items: list[MediaItem] = []
    log(f'Start WPD scan device_id={device_id}')
    with com_context():
        device, API, Types = _open_device(device_id)
        keys_dict = _get_wpd_keys(Types)
        try:
            content = device.Content()
            props = content.Properties()
            
            # Find Internal Storage root (for iPhone: "Internal Storage")
            root_id, root_name = _find_internal_storage_root(content, props, Types, log)
            log(f'Using root: id={root_id}, name="{root_name}"')
            
            # Log first 20 children of the root for diagnostics
            log('First 20 children of root:')
            root_children_names: list[str] = []
            root_children_count = 0
            try:
                child_enum = content.EnumObjects(0, root_id, None)
                for child_id in _enum_object_ids(child_enum):
                    root_children_count += 1
                    if len(root_children_names) < 20:
                        child_values = _get_values(props, child_id, [keys_dict['OBJECT_NAME']], Types)
                        child_name = _safe_get_string(child_values, keys_dict['OBJECT_NAME'])
                        root_children_names.append(child_name)
                        log(f'  - {child_name}')
            except Exception as e:
                log(f'Error enumerating root children: {e}')
            
            log(f'Root has {root_children_count} direct children')

            # Single-pass scan: enumerate and detect media in one traversal
            visited: set[str] = set()
            initial_path = root_name if root_id != WPD_DEVICE_OBJECT_ID else ''
            
            added_debug = 0
            skipped_no_ext = 0
            skipped_not_media = 0
            objects_seen = 0
            containers_seen = 0
            # Track objects with no extension for diagnostic logging
            no_ext_examples: list[tuple[str, str, int]] = []  # (object_id, name, prop_count)
            # Track first few objects for deep debugging
            debug_first_objects = 0

            def scan_recursive(parent_id: str, current_path: str, depth: int = 0) -> None:
                nonlocal objects_seen, containers_seen, added_debug, skipped_no_ext, skipped_not_media, debug_first_objects
                _check_cancel(cancel_token)
                if depth > 16:
                    return
                if parent_id in visited:
                    return
                visited.add(parent_id)
                containers_seen += 1
                
                # Report progress based on containers processed
                if progress_cb and containers_seen % 50 == 0:
                    progress_cb(containers_seen, 0, current_path or '/')
                
                enum = content.EnumObjects(0, parent_id, None)
                for child_id in _enum_object_ids(enum):
                    _check_cancel(cancel_token)
                    
                    # Get ALL properties for this object (more reliable for iPhone)
                    try:
                        values = _get_all_values(props, child_id)
                    except Exception as exc:
                        log(f'GetValues failed for {child_id}: {exc}')
                        continue
                    
                    objects_seen += 1
                    
                    # Extract info trying multiple strategies
                    info = _extract_object_info_from_all(values, keys_dict, Types)
                    real_name = info['original_name'] if info['original_name'] else info['name']
                    content_type = info['content_type']
                    
                    # Debug: log first few objects with all their properties
                    if debug_first_objects < 5:
                        debug_first_objects += 1
                        try:
                            prop_count = values.GetCount()
                            log(f'DEBUG obj {child_id}: name="{real_name}", props={prop_count}, content_type={content_type}')
                            # Log first 10 properties
                            for i in range(min(prop_count, 10)):
                                try:
                                    key = Types._tagpropertykey()
                                    values.GetAt(i, ctypes.byref(key), None)
                                    try:
                                        val = values.GetStringValue(ctypes.pointer(key))
                                    except:
                                        try:
                                            val = values.GetUnsignedIntegerValue(ctypes.pointer(key))
                                        except:
                                            val = '<?>'
                                    log(f'  [{i}] {{{key.fmtid}}}:{key.pid} = {val}')
                                except:
                                    pass
                        except Exception as e:
                            log(f'DEBUG error: {e}')
                    
                    extension = Path(real_name).suffix.lower() if real_name else ''
                    
                    # Check if it's a container first (recurse)
                    if _is_container_object(content_type, real_name, extension):
                        scan_recursive(child_id, _join_path(current_path, real_name), depth + 1)
                        continue
                    
                    # Check if it's a media file by extension
                    is_media_ext = extension in PHOTO_EXTS or extension in VIDEO_EXTS
                    
                    # Fallback: check content_type if no extension match
                    is_media_content = content_type in MEDIA_CONTENT_TYPES if content_type else False
                    
                    if is_media_ext or is_media_content:
                        size = info['size']
                        created = info['created'] or info['modified']
                        
                        # Use extension from content_type if missing
                        final_ext = extension
                        if not final_ext and is_media_content:
                            if content_type == WPD_CONTENT_TYPE_IMAGE:
                                final_ext = '.jpg'
                            elif content_type == WPD_CONTENT_TYPE_VIDEO:
                                final_ext = '.mp4'
                        
                        items.append(
                            MediaItem(
                                device_id=device_id,
                                object_id=child_id,
                                name=real_name or child_id,
                                extension=final_ext,
                                size=size,
                                created=created,
                                device_path=_join_path(current_path, real_name or child_id),
                                content_type=str(content_type) if content_type else '',
                            )
                        )
                        added_debug += 1
                        if added_debug <= 20:
                            log(f'ADD [{final_ext}] {_join_path(current_path, real_name)} size={size} created={created}')
                        continue
                    
                    # Track skipped items
                    if not extension:
                        skipped_no_ext += 1
                        if len(no_ext_examples) < 10:
                            try:
                                prop_count = values.GetCount()
                            except:
                                prop_count = -1
                            no_ext_examples.append((child_id, real_name, prop_count))
                    else:
                        skipped_not_media += 1

            # Start the single-pass scan
            log('Starting single-pass scan...')
            scan_recursive(root_id, initial_path, 0)
            
            log(
                f'Finished scan. found_media={len(items)} objects_seen={objects_seen} '
                f'containers_seen={containers_seen} skipped_no_ext={skipped_no_ext} skipped_not_media={skipped_not_media}'
            )
            
            # If no media found, log examples of objects without extension for debugging
            if len(items) == 0 and no_ext_examples:
                log('No media found! Examples of objects without name/extension:')
                for obj_id, ex_name, prop_count in no_ext_examples:
                    log(f'  id={obj_id}, name="{ex_name}", prop_count={prop_count}')
        except ScanCancelled:
            log('Scan cancelled by user')
            raise
        except Exception as exc:
            tb = traceback.format_exc()
            log(f'ERROR: {exc}')
            log(tb)
            raise ScanError('error_scan_failed', detail=str(log_path)) from exc
        finally:
            try:
                device.Close()
            except Exception:
                pass
    return items


def download_file(
    device_id: str,
    object_id: str,
    dest_path: Path,
    progress_cb,
    cancel_token,
) -> bool:
    """
    Download a file from device.
    Tries Shell API first if object_id looks like a shell parsing name.
    """
    # Shell parsing names start with ::{ (CLSID format) - this is reliable detection
    if object_id.startswith('::{'):
        try:
            from infrastructure.wpd.shell_wrapper import download_file_shell
            return download_file_shell(object_id, dest_path, progress_cb, cancel_token)
        except Exception:
            pass  # Fall through to WPD
    
    # WPD download
    try:
        with open_device_session(device_id) as session:
            return session.download(object_id, dest_path, progress_cb, cancel_token)
    except COMError:
        return False


class DeviceSession:
    def __init__(self, device, resources, keys_dict) -> None:
        self._device = device
        self._resources = resources
        self._keys = keys_dict

    def download(
        self,
        object_id: str,
        dest_path: Path,
        progress_cb,
        cancel_token,
    ) -> bool:
        optimal = ctypes.c_ulong(0)
        stream = None
        try:
            result = self._resources.GetStream(
                object_id,
                self._keys['RESOURCE_DEFAULT'],
                STGM_READ,
                ctypes.byref(optimal),
            )
            if isinstance(result, tuple):
                stream = result[0]
                if len(result) > 1 and isinstance(result[1], int):
                    optimal = ctypes.c_ulong(result[1])
            else:
                stream = result
        except COMError:
            raise
        except Exception:
            stream = self._resources.GetStream(
                object_id,
                self._keys['RESOURCE_DEFAULT'],
                STGM_READ,
                ctypes.byref(optimal),
            )

        chunk_size = max(int(optimal.value) if optimal.value else 65536, 65536)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        bytes_done = 0
        with dest_path.open('wb') as handle:
            while True:
                if cancel_token and cancel_token.cancelled:
                    return False
                try:
                    data = stream.Read(chunk_size)
                except COMError:
                    raise
                if isinstance(data, tuple):
                    data = data[0]
                if not data:
                    break
                handle.write(data)
                bytes_done += len(data)
                if progress_cb:
                    progress_cb(bytes_done)
        return True


@contextmanager
def open_device_session(device_id: str) -> Iterator[DeviceSession]:
    with com_context():
        device, API, Types = _open_device(device_id)
        keys_dict = _get_wpd_keys(Types)
        try:
            content = device.Content()
            resources = content.Transfer()
            yield DeviceSession(device, resources, keys_dict)
        finally:
            try:
                device.Close()
            except Exception:
                pass
