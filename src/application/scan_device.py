from __future__ import annotations

from datetime import datetime
from typing import List

from domain import MediaItem, ScanResult, DeviceInfo
from infrastructure.wpd.com_wrapper import list_media_items


def scan_device(device: DeviceInfo) -> ScanResult:
    items: List[MediaItem] = list_media_items(device.id)
    photos = sum(1 for i in items if i.is_photo)
    videos = sum(1 for i in items if i.is_video)
    total_size = sum(i.size for i in items)
    dates = [i.created for i in items if i.created]
    date_min = min(dates) if dates else None
    date_max = max(dates) if dates else None
    return ScanResult(
        device=device,
        items=items,
        total_photos=photos,
        total_videos=videos,
        total_size=total_size,
        date_min=date_min,
        date_max=date_max,
    )