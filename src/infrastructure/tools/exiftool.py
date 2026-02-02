from __future__ import annotations

import subprocess
from pathlib import Path


CREATE_NO_WINDOW = 0x08000000


def exiftool_available(app_root: Path) -> bool:
    return (app_root / 'tools' / 'exiftool.exe').is_file()


def copy_metadata(app_root: Path, src: Path, dest: Path, log) -> bool:
    exe = app_root / 'tools' / 'exiftool.exe'
    if not exe.exists():
        return False
    cmd = [
        str(exe),
        '-overwrite_original',
        '-TagsFromFile', str(src),
        '-all:all',
        str(dest),
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            creationflags=CREATE_NO_WINDOW,
            text=True,
        )
        if result.stdout:
            for line in result.stdout.splitlines():
                log(f'exiftool: {line}')
        return result.returncode == 0
    except Exception as exc:
        log(f'exiftool error: {exc}')
        return False