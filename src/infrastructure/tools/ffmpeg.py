from __future__ import annotations

import subprocess
from pathlib import Path


CREATE_NO_WINDOW = 0x08000000


def ffmpeg_available(app_root: Path) -> bool:
    return (app_root / 'tools' / 'ffmpeg.exe').is_file()


def _run_ffmpeg(app_root: Path, args: list[str], log) -> tuple[bool, str]:
    exe = app_root / 'tools' / 'ffmpeg.exe'
    if not exe.exists():
        log('ffmpeg.exe no encontrado')
        return False, ''
    cmd = [str(exe)] + args
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            creationflags=CREATE_NO_WINDOW,
            text=True,
        )
        output = result.stdout or ''
        if output:
            for line in output.splitlines():
                log(f'ffmpeg: {line}')
        return result.returncode == 0, output
    except Exception as exc:
        log(f'ffmpeg error: {exc}')
        return False, ''


def _heic_unsupported(output: str) -> bool:
    text = output.lower()
    if 'heic' not in text and 'heif' not in text:
        return False
    markers = [
        'not supported',
        'unknown decoder',
        'decoder',
        'could not find decoder',
        'not found',
        'unsupported',
    ]
    return any(marker in text for marker in markers)


def convert_heic_to_jpg(app_root: Path, src: Path, dest: Path, log) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = [
        '-y',
        '-i', str(src),
        '-q:v', '2',
        str(dest),
    ]
    ok, output = _run_ffmpeg(app_root, args, log)
    if not ok and _heic_unsupported(output):
        log('ffmpeg does not support HEIC/HEIF in this build')
    return ok


def convert_video_to_mp4(app_root: Path, src: Path, dest: Path, log) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = [
        '-y',
        '-i', str(src),
        '-c:v', 'libx264',
        '-preset', 'slow',
        '-crf', '18',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-map_metadata', '0',
        '-movflags', '+use_metadata_tags',
        str(dest),
    ]
    ok, _ = _run_ffmpeg(app_root, args, log)
    return ok
