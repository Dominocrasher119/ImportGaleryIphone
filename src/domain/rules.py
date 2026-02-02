from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

WINDOWS_INVALID_RE = re.compile(r'[<>:"/\\|?*]')
WINDOWS_CONTROL_RE = re.compile(r'[\x00-\x1f]')
RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
}

MAX_FILE_NAME = 150
MAX_FOLDER_NAME = 60


def truncate_filename(name: str, max_length: int = MAX_FILE_NAME) -> str:
    if len(name) <= max_length:
        return name
    ext = Path(name).suffix
    if not ext:
        return name[:max_length]
    stem = Path(name).stem
    max_stem = max_length - len(ext)
    if max_stem <= 0:
        return ext[-max_length:]
    return f'{stem[:max_stem]}{ext}'


def sanitize_filename(
    name: str,
    fallback: str = 'file',
    max_length: int | None = None,
    preserve_extension: bool = False,
) -> str:
    if not name:
        return fallback
    name = WINDOWS_CONTROL_RE.sub('_', name)
    name = WINDOWS_INVALID_RE.sub('_', name)
    name = name.strip(' .')
    if not name:
        return fallback
    if max_length and len(name) > max_length:
        if preserve_extension:
            name = truncate_filename(name, max_length)
        else:
            name = name[:max_length]
        name = name.strip(' .')
        if not name:
            return fallback
    if name.upper() in RESERVED_NAMES:
        name = f'_{name}'
    return name


def format_datetime(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.strftime('%Y-%m-%d_%H-%M-%S')


def build_base_filename(original_name: str, created: datetime | None) -> str:
    base = Path(original_name).stem if original_name else 'original'
    base = sanitize_filename(base, 'original')
    prefix = format_datetime(created) if created else 'unknown_date'
    return f'{prefix}_{base}'


def build_tokens(
    created: datetime | None,
    device_name: str,
    media_type: str,
    type_label: str,
) -> dict[str, str]:
    if created:
        year = created.strftime('%Y')
        month = created.strftime('%m')
        day = created.strftime('%d')
        week = f'{created.isocalendar().week:02d}'
    else:
        year = 'unknown'
        month = 'unknown'
        day = 'unknown'
        week = 'unknown'
    return {
        'YYYY': sanitize_filename(year, 'unknown'),
        'MM': sanitize_filename(month, 'unknown'),
        'DD': sanitize_filename(day, 'unknown'),
        'WW': sanitize_filename(week, 'unknown'),
        'DEVICE': sanitize_filename(device_name or 'Device', 'Device'),
        'TYPE': sanitize_filename(type_label or media_type or 'Media', 'Media'),
    }


def apply_template(template: str, tokens: dict[str, str]) -> Path:
    if not template:
        return Path('')
    text = template
    for key, value in tokens.items():
        text = text.replace(f'{{{key}}}', value)
    text = text.replace('\\', '/').strip('/')
    if not text:
        return Path('')
    parts = [sanitize_filename(p, 'folder', max_length=MAX_FOLDER_NAME) for p in text.split('/') if p]
    return Path(*parts)


def preset_to_template(preset_key: str) -> str:
    mapping = {
        'A': '{YYYY}/{MM}/',
        'B': '{YYYY}/{MM}/{DD}/',
        'C': 'Import_iPhone/',
        'D': '{TYPE}/{YYYY}/{MM}/',
        'E': '{YYYY}/Week_{WW}/',
        'F': '{DEVICE}/{YYYY}/{MM}/',
    }
    return mapping.get(preset_key, mapping['A'])


def ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f'{stem}_{counter}{suffix}'
        if not candidate.exists():
            return candidate
        counter += 1
