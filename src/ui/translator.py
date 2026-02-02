from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from PySide6 import QtCore

from infrastructure.fs.path_utils import resource_path


class Translator(QtCore.QObject):
    language_changed = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._translations: Dict[str, Dict[str, str]] = {}
        self._language = 'en'
        self._load_languages()

    def _load_languages(self) -> None:
        for code in ('en', 'es', 'ca'):
            path = resource_path(
                f'ui/i18n/{code}.json',
                f'src/ui/i18n/{code}.json',
                f'i18n/{code}.json',
            )
            try:
                data = json.loads(path.read_text(encoding='utf-8-sig'))
            except Exception:
                data = {}
            self._translations[code] = data

    def set_language(self, code: str) -> None:
        if code not in self._translations:
            code = 'en'
        if self._language == code:
            return
        self._language = code
        self.language_changed.emit(code)

    def language(self) -> str:
        return self._language

    def tr(self, key: str) -> str:
        return (
            self._translations.get(self._language, {}).get(key)
            or self._translations.get('en', {}).get(key)
            or key
        )


def detect_system_language() -> str:
    locale = QtCore.QLocale.system().name().lower()
    if locale.startswith('es'):
        return 'es'
    if locale.startswith('ca'):
        return 'ca'
    return 'en'


def format_bytes(num: int) -> str:
    step = 1024.0
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num < step:
            return f'{num:.1f} {unit}'
        num /= step
    return f'{num:.1f} PB'


def format_date_range(date_min, date_max) -> str:
    if not date_min or not date_max:
        return '-'
    try:
        return f'{date_min.date()} → {date_max.date()}'
    except Exception:
        return '-'