from __future__ import annotations

from datetime import datetime
from typing import Callable, List, Optional, Tuple

from domain import CancelToken, MediaItem, ScanResult, DeviceInfo
from infrastructure.wpd.com_wrapper import list_media_items


ProgressCb = Optional[Callable[[int, int, str], None]]
ItemsCb = Optional[Callable[[List[MediaItem]], None]]


def scan_device(
    device: DeviceInfo,
    progress_cb: ProgressCb = None,
    items_cb: ItemsCb = None,
    cancel_token: CancelToken | None = None,
) -> ScanResult:
    items: List[MediaItem] = list_media_items(
        device.id,
        progress_cb=progress_cb,
        items_cb=items_cb,
        cancel_token=cancel_token,
    )
    photos = sum(1 for i in items if i.is_photo)
    videos = sum(1 for i in items if i.is_video)
    total_size = sum(i.size for i in items if i.size and i.size > 0)
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
