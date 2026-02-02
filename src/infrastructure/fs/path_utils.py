from __future__ import annotations

import os
import sys
from pathlib import Path


def get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def ensure_cache_dir() -> Path:
    root = get_app_root()
    cache = root / '_cache'
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def resource_path(*candidates: str) -> Path:
    root = get_app_root()
    for rel in candidates:
        path = root / rel
        if path.exists():
            return path
    return root / candidates[0]