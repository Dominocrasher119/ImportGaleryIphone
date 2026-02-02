from datetime import datetime

from domain.rules import (
    MAX_FILE_NAME,
    MAX_FOLDER_NAME,
    apply_template,
    build_base_filename,
    build_tokens,
    sanitize_filename,
    truncate_filename,
)


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


def test_truncate_filename_preserves_extension():
    long_base = 'A' * 300
    name = f'{long_base}.HEIC'
    truncated = truncate_filename(name)
    assert truncated.endswith('.HEIC')
    assert len(truncated) <= MAX_FILE_NAME


def test_apply_template_truncates_folder_names():
    tokens = build_tokens(
        created=datetime(2024, 1, 2, 3, 4, 5),
        device_name='Device' * 50,
        media_type='photo',
        type_label='Fotos' * 20,
    )
    template = '{DEVICE}/{TYPE}/{YYYY}/{MM}/'
    path = apply_template(template, tokens)
    for part in path.parts:
        assert len(part) <= MAX_FOLDER_NAME


def test_apply_template_deep_structure():
    tokens = build_tokens(
        created=datetime(2024, 1, 2, 3, 4, 5),
        device_name='iPhone',
        media_type='photo',
        type_label='Fotos',
    )
    template = '/'.join(['{YYYY}', '{MM}', '{DD}'] * 8) + '/'
    path = apply_template(template, tokens)
    assert len(path.parts) == 24


def test_reserved_names_are_prefixed():
    assert sanitize_filename('CON') == '_CON'
    assert sanitize_filename('AUX') == '_AUX'
