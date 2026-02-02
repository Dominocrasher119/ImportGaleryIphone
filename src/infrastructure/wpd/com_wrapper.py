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
from domain.errors import ScanCancelled
from infrastructure.fs.path_utils import ensure_cache_dir

WPD_DEVICE_OBJECT_ID = 'DEVICE'
STGM_READ = 0x00000000

# Content type GUIDs for containers
WPD_CONTENT_TYPE_FOLDER = GUID("{27E2E392-A111-48E0-AB0C-E17705A05F85}")
# Functional objects are used for storage roots on some devices (e.g., iPhone)
WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT = GUID("{99ED0160-17FF-4008-8A21-7F9C1B91036B}")
CONTAINER_CONTENT_TYPES = {WPD_CONTENT_TYPE_FOLDER, WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT}

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
    if content_type in CONTAINER_CONTENT_TYPES:
        return True
    ext = extension if extension is not None else Path(name).suffix
    # Storage roots on some devices don't expose content type but also have no extension
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


def list_media_items(
    device_id: str,
    progress_cb: ProgressCb = None,
    cancel_token: CancelToken | None = None,
) -> list[MediaItem]:
    log, log_path = _make_scan_logger()
    items: list[MediaItem] = []
    log(f'Start scan device_id={device_id}')
    with com_context():
        device, API, Types = _open_device(device_id)
        keys_dict = _get_wpd_keys(Types)
        try:
            content = device.Content()
            props = content.Properties()
            root_id = WPD_DEVICE_OBJECT_ID

            # Pre-pass: collect all container IDs and paths to compute a real progress total
            containers: list[tuple[str, str, int]] = []
            visited: set[str] = set()
            stack: list[tuple[str, str, int]] = [(root_id, '', 0)]

            while stack:
                _check_cancel(cancel_token)
                parent_id, path, depth = stack.pop()
                if parent_id in visited:
                    continue
                visited.add(parent_id)
                containers.append((parent_id, path, depth))
                if depth >= 16:
                    continue
                enum = content.EnumObjects(0, parent_id, None)
                for child_id in _enum_object_ids(enum):
                    _check_cancel(cancel_token)
                    prop_keys = [keys_dict['OBJECT_NAME'], keys_dict['OBJECT_CONTENT_TYPE']]
                    values = _get_values(props, child_id, prop_keys, Types)
                    name = _safe_get_string(values, keys_dict['OBJECT_NAME'])
                    content_type = _safe_get_guid(values, keys_dict['OBJECT_CONTENT_TYPE'])
                    if _is_container_object(content_type, name):
                        stack.append((child_id, _join_path(path, name), depth + 1))

            total_containers = len(containers)
            log(f'Containers to scan: {total_containers}')
            if progress_cb:
                progress_cb(0, total_containers, '')

            visited.clear()
            added_debug = 0
            skipped_no_ext = 0
            skipped_not_media = 0
            skipped_unknown = 0
            objects_seen = 0

            def walk(parent_id: str, current_path: str, depth: int = 0) -> None:
                _check_cancel(cancel_token)
                if depth > 16:
                    return
                if parent_id in visited:
                    return
                visited.add(parent_id)
                enum = content.EnumObjects(0, parent_id, None)
                for child_id in _enum_object_ids(enum):
                    _check_cancel(cancel_token)
                    prop_keys = [keys_dict['OBJECT_NAME'], keys_dict['OBJECT_SIZE'], 
                                 keys_dict['OBJECT_CONTENT_TYPE'], keys_dict['OBJECT_DATE_CREATED'], 
                                 keys_dict['OBJECT_DATE_MODIFIED']]
                    try:
                        values = _get_values(props, child_id, prop_keys, Types)
                    except Exception as exc:
                        log(f'GetValues failed for {child_id}: {exc}')
                        continue
                    nonlocal objects_seen
                    objects_seen += 1
                    name = _safe_get_string(values, keys_dict['OBJECT_NAME'])
                    size = _safe_get_unsigned(values, keys_dict['OBJECT_SIZE'])
                    created = _safe_get_date(values, keys_dict['OBJECT_DATE_CREATED'])
                    if created is None:
                        created = _safe_get_date(values, keys_dict['OBJECT_DATE_MODIFIED'])
                    content_type = _safe_get_guid(values, keys_dict['OBJECT_CONTENT_TYPE'])
                    extension = Path(name).suffix.lower()
                    is_media_ext = extension in PHOTO_EXTS or extension in VIDEO_EXTS
                    if is_media_ext:
                        items.append(
                            MediaItem(
                                device_id=device_id,
                                object_id=child_id,
                                name=name,
                                extension=extension,
                                size=size,
                                created=created,
                                device_path=_join_path(current_path, name),
                                content_type=str(content_type) if content_type else '',
                            )
                        )
                        nonlocal added_debug
                        added_debug += 1
                        if added_debug <= 20:
                            log(f'ADD [{extension}] {_join_path(current_path, name)} size={size} created={created}')
                        continue
                    # Not media extension; decide whether to descend or skip
                    if _is_container_object(content_type, name, extension):
                        walk(child_id, _join_path(current_path, name), depth + 1)
                        continue
                    if not extension:
                        nonlocal skipped_no_ext
                        skipped_no_ext += 1
                        continue
                    nonlocal skipped_not_media
                    skipped_not_media += 1

            for idx, (container_id, container_path, depth) in enumerate(containers, start=1):
                _check_cancel(cancel_token)
                # Emit progress before diving into the container to show immediate movement
                if progress_cb:
                    progress_cb(idx, total_containers, container_path or '/')
                walk(container_id, container_path, depth)
            log(
                f'Finished scan. Items found: {len(items)} objects_seen={objects_seen} '
                f'(skipped_no_ext={skipped_no_ext}, skipped_not_media={skipped_not_media}, skipped_unknown={skipped_unknown})'
            )
        except ScanCancelled:
            log('Scan cancelled by user')
            raise
        except Exception as exc:
            tb = traceback.format_exc()
            log(f'ERROR: {exc}')
            log(tb)
            raise RuntimeError(f'Scan failed. See log: {log_path}') from exc
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
    with com_context():
        device, API, Types = _open_device(device_id)
        keys_dict = _get_wpd_keys(Types)
        try:
            content = device.Content()
            resources = content.Transfer()
            optimal = ctypes.c_ulong(0)
            stream = None
            try:
                result = resources.GetStream(object_id, keys_dict['RESOURCE_DEFAULT'], STGM_READ, ctypes.byref(optimal))
                if isinstance(result, tuple):
                    stream = result[0]
                    if len(result) > 1 and isinstance(result[1], int):
                        optimal = ctypes.c_ulong(result[1])
                else:
                    stream = result
            except Exception:
                stream = resources.GetStream(object_id, keys_dict['RESOURCE_DEFAULT'], STGM_READ, ctypes.byref(optimal))

            chunk_size = max(int(optimal.value) if optimal.value else 65536, 65536)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            bytes_done = 0
            with dest_path.open('wb') as handle:
                while True:
                    if cancel_token and cancel_token.cancelled:
                        return False
                    data = stream.Read(chunk_size)
                    if isinstance(data, tuple):
                        data = data[0]
                    if not data:
                        break
                    handle.write(data)
                    bytes_done += len(data)
                    if progress_cb:
                        progress_cb(bytes_done)
            return True
        except COMError:
            return False
        finally:
            try:
                device.Close()
            except Exception:
                pass
