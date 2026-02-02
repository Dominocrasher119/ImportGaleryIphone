from __future__ import annotations

import os
import sys
from pathlib import Path


def get_app_root() -> Path:
    """Get the application root directory.
    
    When frozen (PyInstaller): returns the directory containing the .exe
    When running from source: returns the project root (parent of src/)
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    # Running from source - go up from path_utils.py to project root
    return Path(__file__).resolve().parents[3]


def get_src_root() -> Path:
    """Get the src directory path."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def ensure_cache_dir() -> Path:
    root = get_app_root()
    cache = root / '_cache'
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def resource_path(*candidates: str) -> Path:
    """Find a resource file by checking multiple candidate paths.
    
    Searches in both app_root and src_root to handle both frozen and dev mode.
    """
    roots = [get_app_root(), get_src_root()]
    
    for root in roots:
        for rel in candidates:
            path = root / rel
            if path.exists():
                return path
    
    # Fallback: return first candidate from app_root
    return get_app_root() / candidates[0]