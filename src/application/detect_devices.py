from __future__ import annotations

from typing import List

from domain import DeviceInfo


def detect_devices() -> List[DeviceInfo]:
    """Detect all WPD devices. Returns empty list on COM errors."""
    try:
        from infrastructure.wpd.com_wrapper import list_devices
        return list_devices()
    except Exception:
        return []


def detect_iphone_devices() -> List[DeviceInfo]:
    """Detect iPhone devices. Returns empty list on COM errors."""
    devices = detect_devices()
    return [d for d in devices if d.is_iphone]
