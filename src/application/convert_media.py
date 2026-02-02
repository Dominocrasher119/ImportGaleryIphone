from __future__ import annotations

from pathlib import Path

from domain import MediaItem
from infrastructure.tools.ffmpeg import convert_heic_to_jpg, convert_video_to_mp4, ffmpeg_available
from infrastructure.tools.exiftool import copy_metadata, exiftool_available


def conversion_available(app_root: Path) -> bool:
    return ffmpeg_available(app_root) and exiftool_available(app_root)


def compat_output_path(dest_path: Path, new_ext: str) -> Path:
    return dest_path.with_name(f'{dest_path.stem}_COMPAT{new_ext}')


def convert_media(
    item: MediaItem,
    src_path: Path,
    dest_path: Path,
    app_root: Path,
    log,
    debug_log=None,
) -> tuple[bool, Path | None]:
    debug = debug_log or log
    ext = item.extension.lower()
    if ext in ('.heic', '.heif'):
        output = compat_output_path(dest_path, '.jpg')
        ok = convert_heic_to_jpg(app_root, src_path, output, debug)
        if ok:
            meta_ok = copy_metadata(app_root, src_path, output, debug)
            if not meta_ok:
                debug(f'EXIFTOOL: metadata copy failed for {output.name}')
                return False, None
        return ok, output if ok else None

    if item.is_video and ext in ('.mov', '.m4v'):
        output = compat_output_path(dest_path, '.mp4')
        ok = convert_video_to_mp4(app_root, src_path, output, debug)
        if ok:
            meta_ok = copy_metadata(app_root, src_path, output, debug)
            if not meta_ok:
                debug(f'EXIFTOOL: metadata copy failed for {output.name}')
                return False, None
        return ok, output if ok else None

    return False, None
