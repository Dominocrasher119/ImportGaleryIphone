from datetime import datetime
from pathlib import Path

from domain import DeviceInfo, ImportOptions, MediaItem
from application.build_plan import build_plan


def _item(name: str, ext: str, created: datetime, object_id: str) -> MediaItem:
    return MediaItem(
        device_id='dev',
        object_id=object_id,
        name=f'{name}{ext}',
        extension=ext,
        size=100,
        created=created,
        device_path=f'DCIM/100APPLE/{name}{ext}',
        content_type=''
    )


def test_build_plan_preset_year_month():
    device = DeviceInfo(id='1', name='iPhone')
    items = [
        _item('IMG_0001', '.HEIC', datetime(2024, 5, 10, 12, 0, 0), '1'),
    ]
    options = ImportOptions(
        destination=Path('D:/Dest'),
        structure_preset='A',
        template='{YYYY}/{MM}/',
        keep_live=True,
        create_compat=False,
        language='es',
    )
    plan = build_plan(device, items, options)
    assert plan.items[0].dest_rel_path.startswith('2024/05/')


def test_build_plan_live_photos_same_folder():
    device = DeviceInfo(id='1', name='iPhone')
    created = datetime(2024, 6, 1, 10, 30, 0)
    items = [
        _item('IMG_1234', '.HEIC', created, 'photo'),
        _item('IMG_1234', '.MOV', created, 'video'),
    ]
    options = ImportOptions(
        destination=Path('D:/Dest'),
        structure_preset='B',
        template='{YYYY}/{MM}/{DD}/',
        keep_live=True,
        create_compat=False,
        language='es',
    )
    plan = build_plan(device, items, options)
    parents = {Path(p.dest_rel_path).parent.as_posix() for p in plan.items}
    assert len(parents) == 1