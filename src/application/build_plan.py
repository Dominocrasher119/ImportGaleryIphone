from __future__ import annotations

from pathlib import Path
from typing import Iterable

from domain import DeviceInfo, ImportOptions, ImportPlan, MediaItem, PlanItem
from domain.rules import apply_template, build_base_filename, build_tokens, preset_to_template

TYPE_LABELS = {
    'es': {'photo': 'Fotos', 'video': 'Vídeos', 'other': 'Media'},
    'en': {'photo': 'Photos', 'video': 'Videos', 'other': 'Media'},
    'ca': {'photo': 'Fotos', 'video': 'Vídeos', 'other': 'Media'},
}


def _type_label(media_type: str, language: str) -> str:
    labels = TYPE_LABELS.get(language, TYPE_LABELS['en'])
    return labels.get(media_type, labels['other'])


def _sorted_items(items: Iterable[MediaItem]) -> list[MediaItem]:
    return sorted(
        items,
        key=lambda i: (
            i.created is None,
            i.created or 0,
            i.name.lower(),
        ),
    )


def build_plan(device: DeviceInfo, items: Iterable[MediaItem], options: ImportOptions) -> ImportPlan:
    items_list = _sorted_items(items)

    group_date: dict[str, object] = {}
    if options.keep_live:
        by_base: dict[str, list[MediaItem]] = {}
        for item in items_list:
            key = item.base_name.lower()
            by_base.setdefault(key, []).append(item)
        for group in by_base.values():
            has_photo = any(i.is_photo for i in group)
            has_video = any(i.is_video for i in group)
            if not (has_photo and has_video):
                continue
            preferred = next((i.created for i in group if i.is_photo and i.created), None)
            if preferred is None:
                preferred = next((i.created for i in group if i.created), None)
            for item in group:
                group_date[item.object_id] = preferred

    if options.structure_preset == 'ADV':
        template = options.template
    else:
        template = preset_to_template(options.structure_preset)

    plan_items: list[PlanItem] = []
    total_size = 0

    for item in items_list:
        created = group_date.get(item.object_id, item.created)
        type_label = _type_label(item.media_type, options.language)
        tokens = build_tokens(
            created=created,
            device_name=device.name,
            media_type=item.media_type,
            type_label=type_label,
        )
        folder = apply_template(template, tokens)
        base = build_base_filename(item.name, created)
        filename = f'{base}{item.extension}'
        rel_path = folder / filename if str(folder) else Path(filename)
        abs_path = options.destination / rel_path
        plan_items.append(
            PlanItem(
                item=item,
                dest_rel_path=rel_path.as_posix(),
                dest_abs_path=abs_path,
                temp_abs_path=Path(),
            )
        )
        total_size += item.size

    preview_paths = [p.dest_rel_path for p in plan_items[:20]]
    return ImportPlan(
        items=plan_items,
        preview_paths=preview_paths,
        total_files=len(plan_items),
        total_size=total_size,
    )
