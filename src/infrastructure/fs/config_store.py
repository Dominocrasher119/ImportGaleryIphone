from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = {
    'language': 'en',
    'structure_preset': 'A',
    'template': '{YYYY}/{MM}/',
    'last_destination': '',
    'keep_live': True,
    'create_compat': False,
}


def config_path(app_root: Path) -> Path:
    return app_root / 'config.json'


def load_config(app_root: Path) -> dict[str, Any]:
    path = config_path(app_root)
    if not path.exists():
        return DEFAULT_CONFIG.copy()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return DEFAULT_CONFIG.copy()
    cfg = DEFAULT_CONFIG.copy()
    cfg.update({k: v for k, v in data.items() if k in cfg})
    return cfg


def save_config(app_root: Path, data: dict[str, Any]) -> None:
    path = config_path(app_root)
    payload = DEFAULT_CONFIG.copy()
    payload.update({k: v for k, v in data.items() if k in payload})
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')