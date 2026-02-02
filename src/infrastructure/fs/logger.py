from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from domain import DeviceInfo, ImportOptions


def log_timestamp() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


@dataclass
class ImportLogger:
    log_path: Path

    def write(self, message: str) -> None:
        line = f'[{log_timestamp()}] {message}'
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open('a', encoding='utf-8') as handle:
            handle.write(line + '\n')


def create_logger(dest_root: Path, device: DeviceInfo, options: ImportOptions) -> ImportLogger:
    log_dir = dest_root / 'iImport_logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    name = datetime.now().strftime('import_%Y%m%d_%H%M%S.log')
    log_path = log_dir / name
    logger = ImportLogger(log_path=log_path)

    logger.write('=== iImport log ===')
    logger.write(f'Device: {device.name}')
    logger.write(f'Device ID: {device.id}')
    logger.write(f'Destination: {dest_root}')
    logger.write(f'Preset: {options.structure_preset}')
    logger.write(f'Template: {options.template}')
    logger.write(f'Keep Live Photos: {options.keep_live}')
    logger.write(f'Create compatible copies: {options.create_compat}')
    logger.write('---')
    return logger