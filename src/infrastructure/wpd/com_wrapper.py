from __future__ import annotations

import ctypes
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator

import comtypes
import comtypes.client
from comtypes import COMError

from domain import DeviceInfo, MediaItem, PHOTO_EXTS, VIDEO_EXTS
from infrastructure.fs.path_utils import ensure_cache_dir, get_app_root

WPD_DEVICE_OBJECT_ID = 'DEVICE'
STGM_READ = 0x00000000


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
    from comtypes.gen import PortableDeviceApiLib as WPD
    return WPD


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


def list_devices() -> list[DeviceInfo]:
    devices: list[DeviceInfo] = []
    with com_context():
        _ensure_wpd_module()
        mgr = comtypes.client.CreateObject('PortableDeviceManager')
        count = ctypes.c_ulong(0)
        mgr.GetDevices(None, ctypes.byref(count))
        if count.value == 0:
            return []
        device_ids = (ctypes.c_wchar_p * count.value)()
        mgr.GetDevices(device_ids, ctypes.byref(count))
        for idx in range(count.value):
            dev_id = device_ids[idx]
            name = _get_device_string(mgr, dev_id, 'GetDeviceFriendlyName')
            manufacturer = _get_device_string(mgr, dev_id, 'GetDeviceManufacturer')
            description = _get_device_string(mgr, dev_id, 'GetDeviceDescription')
            devices.append(
                DeviceInfo(
                    id=dev_id,
                    name=name or dev_id,
                    manufacturer=manufacturer,
                    description=description,
                )
            )
    return devices


def _create_device_client_info(WPD):
    client_info = comtypes.client.CreateObject('PortableDeviceValues')
    client_info.SetStringValue(WPD.WPD_CLIENT_NAME, 'iImport')
    client_info.SetUnsignedIntegerValue(WPD.WPD_CLIENT_MAJOR_VERSION, 1)
    client_info.SetUnsignedIntegerValue(WPD.WPD_CLIENT_MINOR_VERSION, 0)
    client_info.SetUnsignedIntegerValue(WPD.WPD_CLIENT_REVISION, 0)
    return client_info


def _open_device(device_id: str):
    WPD = _ensure_wpd_module()
    try:
        device = comtypes.client.CreateObject('PortableDeviceFTM')
    except Exception:
        device = comtypes.client.CreateObject('PortableDevice')
    client_info = _create_device_client_info(WPD)
    device.Open(device_id, client_info)
    return device


def _enum_object_ids(enum) -> Iterator[str]:
    while True:
        try:
            fetched = ctypes.c_ulong(0)
            obj_ids = (ctypes.c_wchar_p * 1)()
            enum.Next(1, obj_ids, ctypes.byref(fetched))
            if fetched.value == 0:
                break
            yield obj_ids[0]
        except Exception:
            try:
                result = enum.Next(1)
                if isinstance(result, tuple) and len(result) == 2:
                    ids, fetched = result
                    if fetched == 0:
                        break
                    if isinstance(ids, (list, tuple)):
                        for obj_id in ids:
                            yield obj_id
                    else:
                        yield ids
                else:
                    break
            except Exception:
                break


def _get_values(props, object_id: str, keys: Iterable) -> object:
    key_collection = comtypes.client.CreateObject('PortableDeviceKeyCollection')
    for key in keys:
        key_collection.Add(key)
    return props.GetValues(object_id, key_collection)


def _safe_get_string(values, key, fallback: str = '') -> str:
    try:
        return values.GetStringValue(key)
    except Exception:
        return fallback


def _safe_get_unsigned(values, key, fallback: int = 0) -> int:
    try:
        return int(values.GetUnsignedIntegerValue(key))
    except Exception:
        try:
            return int(values.GetUnsignedLargeIntegerValue(key))
        except Exception:
            return fallback


def _safe_get_guid(values, key):
    try:
        return values.GetGuidValue(key)
    except Exception:
        return None


def _safe_get_date(values, key) -> datetime | None:
    try:
        value = values.GetValue(key)
    except Exception:
        try:
            value = values.GetStringValue(key)
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


def _find_dcim_ids(content, root_id: str, WPD) -> list[str]:
    props = content.Properties()
    result: list[str] = []

    def walk(parent_id: str, depth: int) -> None:
        if depth > 4:
            return
        enum = content.EnumObjects(0, parent_id, None)
        for child_id in _enum_object_ids(enum):
            keys = [WPD.WPD_OBJECT_NAME, WPD.WPD_OBJECT_CONTENT_TYPE]
            values = _get_values(props, child_id, keys)
            name = _safe_get_string(values, WPD.WPD_OBJECT_NAME)
            content_type = _safe_get_guid(values, WPD.WPD_OBJECT_CONTENT_TYPE)
            if name.upper() == 'DCIM':
                result.append(child_id)
            if content_type == WPD.WPD_CONTENT_TYPE_FOLDER:
                walk(child_id, depth + 1)

    walk(root_id, 0)
    return result


def list_media_items(device_id: str) -> list[MediaItem]:
    items: list[MediaItem] = []
    with com_context():
        WPD = _ensure_wpd_module()
        device = _open_device(device_id)
        try:
            content = device.Content()
            props = content.Properties()
            root_id = getattr(WPD, 'WPD_DEVICE_OBJECT_ID', WPD_DEVICE_OBJECT_ID)
            dcim_ids = _find_dcim_ids(content, root_id, WPD)
            if not dcim_ids:
                dcim_ids = [root_id]

            def walk(parent_id: str, current_path: str) -> None:
                enum = content.EnumObjects(0, parent_id, None)
                for child_id in _enum_object_ids(enum):
                    keys = [WPD.WPD_OBJECT_NAME, WPD.WPD_OBJECT_SIZE, WPD.WPD_OBJECT_CONTENT_TYPE]
                    if hasattr(WPD, 'WPD_OBJECT_DATE_CREATED'):
                        keys.append(WPD.WPD_OBJECT_DATE_CREATED)
                    if hasattr(WPD, 'WPD_OBJECT_DATE_MODIFIED'):
                        keys.append(WPD.WPD_OBJECT_DATE_MODIFIED)
                    values = _get_values(props, child_id, keys)
                    name = _safe_get_string(values, WPD.WPD_OBJECT_NAME)
                    size = _safe_get_unsigned(values, WPD.WPD_OBJECT_SIZE)
                    created = None
                    if hasattr(WPD, 'WPD_OBJECT_DATE_CREATED'):
                        created = _safe_get_date(values, WPD.WPD_OBJECT_DATE_CREATED)
                    if created is None and hasattr(WPD, 'WPD_OBJECT_DATE_MODIFIED'):
                        try:
                            created = _safe_get_date(values, WPD.WPD_OBJECT_DATE_MODIFIED)
                        except Exception:
                            created = None
                    content_type = _safe_get_guid(values, WPD.WPD_OBJECT_CONTENT_TYPE)
                    if content_type == WPD.WPD_CONTENT_TYPE_FOLDER:
                        walk(child_id, f'{current_path}/{name}')
                        continue
                    extension = Path(name).suffix.lower()
                    if not extension:
                        continue
                    if extension not in PHOTO_EXTS and extension not in VIDEO_EXTS:
                        continue
                    items.append(
                        MediaItem(
                            device_id=device_id,
                            object_id=child_id,
                            name=name,
                            extension=extension,
                            size=size,
                            created=created,
                            device_path=f'{current_path}/{name}',
                            content_type=str(content_type) if content_type else '',
                        )
                    )

            for dcim_id in dcim_ids:
                walk(dcim_id, 'DCIM')
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
        WPD = _ensure_wpd_module()
        device = _open_device(device_id)
        try:
            content = device.Content()
            resources = content.Transfer()
            optimal = ctypes.c_ulong(0)
            stream = None
            try:
                result = resources.GetStream(object_id, WPD.WPD_RESOURCE_DEFAULT, STGM_READ, ctypes.byref(optimal))
                if isinstance(result, tuple):
                    stream = result[0]
                    if len(result) > 1 and isinstance(result[1], int):
                        optimal = ctypes.c_ulong(result[1])
                else:
                    stream = result
            except Exception:
                stream = resources.GetStream(object_id, WPD.WPD_RESOURCE_DEFAULT, STGM_READ, ctypes.byref(optimal))

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
