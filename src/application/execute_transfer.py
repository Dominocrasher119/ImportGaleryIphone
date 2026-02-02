from __future__ import annotations

import hashlib
from pathlib import Path

from comtypes import COMError

from domain import CancelToken, DeviceInfo, ImportOptions, ImportPlan, TransferProgress, TransferResult
from domain.rules import ensure_unique_path
from infrastructure.fs.atomic_write import atomic_move
from infrastructure.fs.logger import create_logger
from infrastructure.fs.path_utils import get_app_root
from infrastructure.wpd.com_wrapper import open_device_session
from application.convert_media import conversion_available, convert_media
from application.core_messages import tr


def _temp_path_for(dest_rel: str, temp_dir: Path, object_id: str) -> Path:
    seed = f'{object_id}|{dest_rel}'.encode('utf-8', errors='ignore')
    digest = hashlib.sha1(seed).hexdigest()
    return temp_dir / f'{digest}.part'


def execute_transfer(
    plan: ImportPlan,
    device: DeviceInfo,
    options: ImportOptions,
    progress_cb,
    log_cb,
    cancel_token: CancelToken,
) -> TransferResult:
    dest_root = options.destination
    dest_root.mkdir(parents=True, exist_ok=True)
    tmp_dir = dest_root / '.tmp_import'
    tmp_dir.mkdir(parents=True, exist_ok=True)

    logger = create_logger(dest_root, device, options)
    language = options.language or 'en'

    def log_line(message: str) -> None:
        logger.write(message)
        if log_cb:
            log_cb(message)

    def log_debug(message: str) -> None:
        logger.write(message)

    total_files = len(plan.items)
    bytes_total = plan.total_size
    bytes_done = 0

    copied = 0
    skipped = 0
    failed = 0
    converted = 0
    errors: list[str] = []

    can_convert = options.create_compat and conversion_available(get_app_root())
    if options.create_compat and not can_convert:
        log_line(tr(language, 'error_tools_missing'))

    device_disconnected = False
    last_index = 0
    try:
        with open_device_session(device.id) as session:
            for index, plan_item in enumerate(plan.items, start=1):
                last_index = index
                if cancel_token and cancel_token.cancelled:
                    log_line(tr(language, 'error_import_cancelled'))
                    break

                item = plan_item.item
                dest_path = plan_item.dest_abs_path
                temp_path = _temp_path_for(plan_item.dest_rel_path, tmp_dir, item.object_id)

                if dest_path.exists():
                    try:
                        if dest_path.stat().st_size == item.size:
                            skipped += 1
                            bytes_done += item.size
                            log_line(f'SKIP (same size): {dest_path.name}')
                            if progress_cb:
                                progress_cb(
                                    TransferProgress(
                                        current_index=index,
                                        total_files=total_files,
                                        current_file=item.name,
                                        current_bytes=item.size,
                                        current_total=item.size,
                                        bytes_done=bytes_done,
                                        bytes_total=bytes_total,
                                    )
                                )
                            continue
                    except Exception:
                        pass
                    dest_path = ensure_unique_path(dest_path)

                current_bytes = 0

                def on_chunk(bytes_written: int) -> None:
                    nonlocal current_bytes
                    current_bytes = bytes_written
                    if progress_cb:
                        progress_cb(
                            TransferProgress(
                                current_index=index,
                                total_files=total_files,
                                current_file=item.name,
                                current_bytes=current_bytes,
                                current_total=item.size,
                                bytes_done=bytes_done + current_bytes,
                                bytes_total=bytes_total,
                            )
                        )

                try:
                    ok = session.download(item.object_id, temp_path, on_chunk, cancel_token)
                    if cancel_token and cancel_token.cancelled:
                        if temp_path.exists():
                            temp_path.unlink(missing_ok=True)
                        break
                    if not ok:
                        failed += 1
                        errors.append(f'Error copiando {item.name}')
                        log_line(f'ERROR: {item.name}')
                        if temp_path.exists():
                            temp_path.unlink(missing_ok=True)
                        bytes_done += current_bytes
                        continue
                    atomic_move(temp_path, dest_path)
                    copied += 1
                    bytes_done += item.size
                    log_line(f'OK: {dest_path}')

                    if can_convert:
                        ok_conv, compat_path = convert_media(
                            item,
                            dest_path,
                            dest_path,
                            get_app_root(),
                            log_line,
                            log_debug,
                        )
                        if ok_conv and compat_path:
                            converted += 1
                            log_line(f'COMPAT OK: {compat_path}')
                        elif item.extension.lower() in ('.heic', '.heif', '.mov', '.m4v'):
                            log_line(tr(language, 'error_conversion_failed').format(name=dest_path.name))
                except COMError:
                    device_disconnected = True
                    failed += 1
                    errors.append(tr(language, 'error_device_disconnected'))
                    log_line(tr(language, 'error_device_disconnected'))
                    if temp_path.exists():
                        temp_path.unlink(missing_ok=True)
                    break
                except Exception as exc:
                    failed += 1
                    errors.append(f'Error copiando {item.name}: {exc}')
                    log_line(f'ERROR: {item.name} ({exc})')
                    if temp_path.exists():
                        temp_path.unlink(missing_ok=True)
                    bytes_done += current_bytes
    except COMError:
        device_disconnected = True
        errors.append(tr(language, 'error_device_disconnected'))
        log_line(tr(language, 'error_device_disconnected'))

    if device_disconnected:
        remaining = max(total_files - last_index, 0)
        if remaining:
            failed += remaining

    cancelled = bool(cancel_token and cancel_token.cancelled)
    if cancelled:
        for part in tmp_dir.glob('*.part'):
            try:
                part.unlink()
            except Exception:
                pass

    if tmp_dir.exists() and not any(tmp_dir.iterdir()):
        try:
            tmp_dir.rmdir()
        except Exception:
            pass

    log_line('---')
    log_line(f'Total: {total_files}, Copiados: {copied}, Saltados: {skipped}, Fallidos: {failed}, Compat: {converted}')

    return TransferResult(
        total_files=total_files,
        copied=copied,
        skipped=skipped,
        failed=failed,
        converted=converted,
        cancelled=cancelled,
        log_path=logger.log_path,
        errors=errors,
    )
