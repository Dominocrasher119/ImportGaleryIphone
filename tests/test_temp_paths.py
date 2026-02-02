from pathlib import Path

from application.execute_transfer import _temp_path_for


def test_temp_path_is_short_and_under_tmp_dir():
    temp_dir = Path('D:/Dest/.tmp_import')
    long_rel = 'A' * 400 + '/B' * 200 + '/IMG_1234.HEIC'
    temp_path = _temp_path_for(long_rel, temp_dir, 'OBJECT_ID_WITH_LONG_VALUE' * 10)
    assert temp_path.parent == temp_dir
    assert temp_path.name.endswith('.part')
    assert len(temp_path.name) <= 120


def test_temp_path_changes_with_inputs():
    temp_dir = Path('D:/Dest/.tmp_import')
    path_a = _temp_path_for('2024/01/IMG_0001.HEIC', temp_dir, '1')
    path_b = _temp_path_for('2024/01/IMG_0002.HEIC', temp_dir, '1')
    path_c = _temp_path_for('2024/01/IMG_0001.HEIC', temp_dir, '2')
    assert path_a != path_b
    assert path_a != path_c
