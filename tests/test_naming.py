from datetime import datetime

from domain.rules import build_base_filename, sanitize_filename


def test_sanitize_filename_windows_chars():
    name = 'IMG:001*?<>.jpg'
    assert sanitize_filename(name).startswith('IMG_001')


def test_build_base_filename_with_date():
    dt = datetime(2024, 1, 2, 3, 4, 5)
    base = build_base_filename('IMG_1234.HEIC', dt)
    assert base.startswith('2024-01-02_03-04-05_')
    assert 'IMG_1234' in base


def test_build_base_filename_without_date():
    base = build_base_filename('IMG_1234.HEIC', None)
    assert base.startswith('unknown_date_')