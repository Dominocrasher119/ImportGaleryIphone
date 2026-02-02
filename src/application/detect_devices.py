from __future__ import annotations

from typing import List

from domain import DeviceInfo
from infrastructure.wpd.com_wrapper import list_devices


def detect_devices() -> List[DeviceInfo]:
    return list_devices()


def detect_iphone_devices() -> List[DeviceInfo]:
    devices = list_devices()
    return [d for d in devices if d.is_iphone]