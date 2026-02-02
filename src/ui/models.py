from __future__ import annotations

from datetime import datetime
from typing import List

from PySide6 import QtCore

from domain import MediaItem
from ui.translator import format_bytes


class MediaTableModel(QtCore.QAbstractTableModel):
    def __init__(self, translator) -> None:
        super().__init__()
        self._items: List[MediaItem] = []
        self._tr = translator

    def set_items(self, items: List[MediaItem]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._items)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return 5

    def headerData(self, section: int, orientation, role=QtCore.Qt.DisplayRole):
        if role != QtCore.Qt.DisplayRole or orientation != QtCore.Qt.Horizontal:
            return None
        keys = ['table_name', 'table_type', 'table_date', 'table_size', 'table_path']
        if 0 <= section < len(keys):
            return self._tr.tr(keys[section])
        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0:
                return item.name
            if index.column() == 1:
                return self._type_label(item)
            if index.column() == 2:
                return item.created.strftime('%Y-%m-%d %H:%M:%S') if item.created else '-'
            if index.column() == 3:
                return format_bytes(item.size)
            if index.column() == 4:
                return item.device_path
        return None

    def _type_label(self, item: MediaItem) -> str:
        if item.is_photo:
            return self._tr.tr('scan_photos')
        if item.is_video:
            return self._tr.tr('scan_videos')
        return '—'