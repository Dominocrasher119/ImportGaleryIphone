from __future__ import annotations

import json
from typing import Dict

from infrastructure.fs.path_utils import resource_path


_CACHE: Dict[str, Dict[str, str]] = {}


def _load_lang(code: str) -> Dict[str, str]:
    if code in _CACHE:
        return _CACHE[code]
    path = resource_path(
        f'ui/i18n/{code}.json',
        f'src/ui/i18n/{code}.json',
        f'i18n/{code}.json',
    )
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception:
        data = {}
    _CACHE[code] = data
    return data


def tr(language: str, key: str) -> str:
    lang = language or 'en'
    return (
        _load_lang(lang).get(key)
        or _load_lang('en').get(key)
        or key
    )
