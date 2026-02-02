from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


PHOTO_EXTS = {'.jpg', '.jpeg', '.heic', '.heif', '.png', '.tif', '.tiff', '.gif', '.dng'}
VIDEO_EXTS = {'.mov', '.mp4', '.m4v', '.avi', '.3gp'}


@dataclass
class DeviceInfo:
    id: str
    name: str
    manufacturer: str | None = None
    model: str | None = None
    description: str | None = None

    @property
    def is_iphone(self) -> bool:
        name = (self.name or '').lower()
        manu = (self.manufacturer or '').lower()
        desc = (self.description or '').lower()
        dev_id = (self.id or '').lower()
        # Check by name/manufacturer/description
        if 'iphone' in name or 'iphone' in desc:
            return True
        if 'apple' in manu and 'iphone' in name:
            return True
        # Check by Apple USB Vendor ID (VID 05ac) in device ID
        if 'vid_05ac' in dev_id:
            return True
        return False


@dataclass
class MediaItem:
    device_id: str
    object_id: str
    name: str
    extension: str
    size: int
    created: datetime | None
    device_path: str
    content_type: str

    @property
    def base_name(self) -> str:
        return Path(self.name).stem

    @property
    def is_photo(self) -> bool:
        return self.extension.lower() in PHOTO_EXTS

    @property
    def is_video(self) -> bool:
        return self.extension.lower() in VIDEO_EXTS

    @property
    def media_type(self) -> str:
        return 'photo' if self.is_photo else 'video' if self.is_video else 'other'


@dataclass
class ScanResult:
    device: DeviceInfo
    items: list[MediaItem]
    total_photos: int
    total_videos: int
    total_size: int
    date_min: datetime | None
    date_max: datetime | None


@dataclass
class ImportOptions:
    destination: Path
    structure_preset: str
    template: str
    keep_live: bool
    create_compat: bool
    language: str


@dataclass
class PlanItem:
    item: MediaItem
    dest_rel_path: str
    dest_abs_path: Path
    temp_abs_path: Path
    compat_tasks: list[tuple[str, Path]] = field(default_factory=list)


@dataclass
class ImportPlan:
    items: list[PlanItem]
    preview_paths: list[str]
    total_files: int
    total_size: int


@dataclass
class TransferProgress:
    current_index: int
    total_files: int
    current_file: str
    current_bytes: int
    current_total: int
    bytes_done: int
    bytes_total: int


@dataclass
class TransferResult:
    total_files: int
    copied: int
    skipped: int
    failed: int
    converted: int
    cancelled: bool
    log_path: Path | None
    errors: list[str] = field(default_factory=list)


class CancelToken:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


@dataclass
class FileAction:
    src_item: MediaItem
    dest_path: Path
    temp_path: Path
    action: str
    reason: str | None = None


@dataclass
class BuildPlanInput:
    device: DeviceInfo
    items: Iterable[MediaItem]
    options: ImportOptions