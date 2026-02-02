from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from domain import DeviceInfo, ImportPlan, ScanResult
from ui.models import MediaTableModel
from ui.translator import format_bytes, format_date_range


class StepIndicator(QtWidgets.QWidget):
    def __init__(self, translator) -> None:
        super().__init__()
        self._tr = translator
        self._result = None
        self._labels: list[QtWidgets.QLabel] = []
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)

    def set_steps(self, titles: list[str]) -> None:
        for label in self._labels:
            self._layout.removeWidget(label)
            label.deleteLater()
        self._labels = []
        for idx, title in enumerate(titles, start=1):
            label = QtWidgets.QLabel(f'{idx}. {title}')
            label.setProperty('stepActive', False)
            self._layout.addWidget(label)
            self._labels.append(label)
        self._layout.addStretch(1)

    def set_current(self, index: int) -> None:
        for idx, label in enumerate(self._labels):
            label.setProperty('stepActive', idx == index)
            label.style().unpolish(label)
            label.style().polish(label)


class DevicePage(QtWidgets.QWidget):
    device_selected = QtCore.Signal(object)
    refresh_requested = QtCore.Signal()

    def __init__(self, translator) -> None:
        super().__init__()
        self._tr = translator
        self._devices: list[DeviceInfo] = []

        self.title = QtWidgets.QLabel()
        self.title.setObjectName('PageTitle')
        self.instructions = QtWidgets.QLabel()
        self.instructions.setWordWrap(True)

        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list.itemSelectionChanged.connect(self._emit_selection)

        self.refresh_btn = QtWidgets.QPushButton()
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.title)
        layout.addWidget(self.instructions)
        layout.addWidget(self.list, 1)
        layout.addWidget(self.refresh_btn, 0, QtCore.Qt.AlignLeft)

    def retranslate(self) -> None:
        self.title.setText(self._tr.tr('step_device'))
        self.instructions.setText(self._tr.tr('device_instructions'))
        self.refresh_btn.setText(self._tr.tr('refresh'))

    def set_devices(self, devices: list[DeviceInfo]) -> None:
        self._devices = devices
        self.list.clear()
        if not devices:
            item = QtWidgets.QListWidgetItem(self._tr.tr('device_none'))
            item.setFlags(QtCore.Qt.NoItemFlags)
            self.list.addItem(item)
            return
        for device in devices:
            text = device.name
            if device.manufacturer:
                text = f'{text} ({device.manufacturer})'
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.UserRole, device)
            if not device.is_iphone:
                item.setForeground(QtGui.QBrush(QtGui.QColor('#6b7280')))
            self.list.addItem(item)

    def selected_device(self) -> DeviceInfo | None:
        items = self.list.selectedItems()
        if not items:
            return None
        return items[0].data(QtCore.Qt.UserRole)

    def _emit_selection(self) -> None:
        device = self.selected_device()
        if device:
            self.device_selected.emit(device)


class ScanPage(QtWidgets.QWidget):
    scan_requested = QtCore.Signal()

    def __init__(self, translator) -> None:
        super().__init__()
        self._tr = translator
        self._model = MediaTableModel(translator)
        self._result: ScanResult | None = None

        self.title = QtWidgets.QLabel()
        self.title.setObjectName('PageTitle')

        self.scan_btn = QtWidgets.QPushButton()
        self.scan_btn.clicked.connect(self.scan_requested.emit)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        self.summary_group = QtWidgets.QGroupBox()
        self.summary_layout = QtWidgets.QGridLayout(self.summary_group)
        self.lbl_photos = QtWidgets.QLabel()
        self.lbl_videos = QtWidgets.QLabel()
        self.lbl_size = QtWidgets.QLabel()
        self.lbl_dates = QtWidgets.QLabel()

        self.summary_layout.addWidget(self.lbl_photos, 0, 0)
        self.summary_layout.addWidget(self.lbl_videos, 0, 1)
        self.summary_layout.addWidget(self.lbl_size, 1, 0)
        self.summary_layout.addWidget(self.lbl_dates, 1, 1)

        self.table = QtWidgets.QTableView()
        self.table.setModel(self._model)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.title)
        layout.addWidget(self.scan_btn, 0, QtCore.Qt.AlignLeft)
        layout.addWidget(self.progress)
        layout.addWidget(self.summary_group)
        layout.addWidget(self.table, 1)

    def retranslate(self) -> None:
        self.title.setText(self._tr.tr('step_scan'))
        self.scan_btn.setText(self._tr.tr('scan'))
        self.summary_group.setTitle(self._tr.tr('scan_summary'))
        self._model.headerDataChanged.emit(QtCore.Qt.Horizontal, 0, 4)
        if self._result:
            self.set_scan_result(self._result)
        if self._model.rowCount() > 0:
            top_left = self._model.index(0, 0)
            bottom_right = self._model.index(self._model.rowCount() - 1, self._model.columnCount() - 1)
            self._model.dataChanged.emit(top_left, bottom_right)

    def set_scanning(self, scanning: bool) -> None:
        if scanning:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(1)

    def set_scan_result(self, result: ScanResult | None) -> None:
        self._result = result
        if not result:
            self._model.set_items([])
            self.lbl_photos.setText('')
            self.lbl_videos.setText('')
            self.lbl_size.setText('')
            self.lbl_dates.setText('')
            return
        self._model.set_items(result.items)
        self.lbl_photos.setText(f"{self._tr.tr('scan_photos')}: {result.total_photos}")
        self.lbl_videos.setText(f"{self._tr.tr('scan_videos')}: {result.total_videos}")
        self.lbl_size.setText(f"{self._tr.tr('scan_total_size')}: {format_bytes(result.total_size)}")
        self.lbl_dates.setText(f"{self._tr.tr('scan_date_range')}: {format_date_range(result.date_min, result.date_max)}")


class OptionsPage(QtWidgets.QWidget):
    options_changed = QtCore.Signal()
    browse_requested = QtCore.Signal()

    def __init__(self, translator) -> None:
        super().__init__()
        self._tr = translator

        self.title = QtWidgets.QLabel()
        self.title.setObjectName('PageTitle')

        self.dest_label = QtWidgets.QLabel()
        self.dest_edit = QtWidgets.QLineEdit()
        self.dest_btn = QtWidgets.QPushButton()
        self.dest_btn.clicked.connect(self.browse_requested.emit)
        self.dest_edit.textChanged.connect(self.options_changed.emit)

        dest_row = QtWidgets.QHBoxLayout()
        dest_row.addWidget(self.dest_edit, 1)
        dest_row.addWidget(self.dest_btn)

        self.structure_label = QtWidgets.QLabel()
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.currentIndexChanged.connect(self.options_changed.emit)

        self.advanced_toggle = QtWidgets.QPushButton()
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)

        self.advanced_widget = QtWidgets.QWidget()
        adv_layout = QtWidgets.QVBoxLayout(self.advanced_widget)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        self.template_label = QtWidgets.QLabel()
        self.template_edit = QtWidgets.QLineEdit()
        self.template_hint = QtWidgets.QLabel()
        self.template_hint.setObjectName('HintLabel')
        self.template_edit.textChanged.connect(self.options_changed.emit)
        adv_layout.addWidget(self.template_label)
        adv_layout.addWidget(self.template_edit)
        adv_layout.addWidget(self.template_hint)
        self.advanced_widget.setVisible(False)

        self.preview_label = QtWidgets.QLabel()
        self.preview_list = QtWidgets.QListWidget()
        self.preview_list.setMinimumHeight(140)

        self.compat_checkbox = QtWidgets.QCheckBox()
        self.compat_help = QtWidgets.QLabel()
        self.compat_help.setWordWrap(True)
        self.compat_help.setObjectName('HintLabel')
        self.compat_warning = QtWidgets.QLabel()
        self.compat_warning.setWordWrap(True)
        self.compat_warning.setObjectName('WarningLabel')

        self.live_checkbox = QtWidgets.QCheckBox()

        self.compat_checkbox.toggled.connect(self.options_changed.emit)
        self.live_checkbox.toggled.connect(self.options_changed.emit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.title)
        layout.addWidget(self.dest_label)
        layout.addLayout(dest_row)
        layout.addWidget(self.structure_label)
        layout.addWidget(self.preset_combo)
        layout.addWidget(self.advanced_toggle, 0, QtCore.Qt.AlignLeft)
        layout.addWidget(self.advanced_widget)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.preview_list)
        layout.addWidget(self.compat_checkbox)
        layout.addWidget(self.compat_help)
        layout.addWidget(self.compat_warning)
        layout.addWidget(self.live_checkbox)
        layout.addStretch(1)

    def retranslate(self) -> None:
        self.title.setText(self._tr.tr('step_options'))
        self.dest_label.setText(self._tr.tr('destination_label'))
        self.dest_btn.setText(self._tr.tr('browse'))
        self.structure_label.setText(self._tr.tr('structure_label'))
        self._load_presets()
        self.advanced_toggle.setText(self._tr.tr('advanced_toggle'))
        self.template_label.setText(self._tr.tr('template_label'))
        self.template_hint.setText(self._tr.tr('template_hint'))
        self.preview_label.setText(self._tr.tr('preview_label'))
        self.compat_checkbox.setText(self._tr.tr('compat_checkbox'))
        self.compat_help.setText(self._tr.tr('compat_help'))
        self.compat_warning.setText(self._tr.tr('compat_missing'))
        self.live_checkbox.setText(self._tr.tr('live_checkbox'))

    def _load_presets(self) -> None:
        current = self.preset_combo.currentData()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem(self._tr.tr('preset_a'), 'A')
        self.preset_combo.addItem(self._tr.tr('preset_b'), 'B')
        self.preset_combo.addItem(self._tr.tr('preset_c'), 'C')
        self.preset_combo.addItem(self._tr.tr('preset_d'), 'D')
        self.preset_combo.addItem(self._tr.tr('preset_e'), 'E')
        self.preset_combo.addItem(self._tr.tr('preset_f'), 'F')
        if current:
            idx = self.preset_combo.findData(current)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
        self.preset_combo.blockSignals(False)

    def _toggle_advanced(self, checked: bool) -> None:
        self.advanced_widget.setVisible(checked)
        self.options_changed.emit()

    def set_destination(self, path: str) -> None:
        self.dest_edit.setText(path)

    def destination(self) -> str:
        return self.dest_edit.text().strip()

    def preset(self) -> str:
        return self.preset_combo.currentData() or 'A'

    def template(self) -> str:
        return self.template_edit.text().strip() or '{YYYY}/{MM}/'

    def use_advanced(self) -> bool:
        return self.advanced_widget.isVisible() and self.advanced_toggle.isChecked()

    def set_preview(self, paths: list[str]) -> None:
        self.preview_list.clear()
        for path in paths:
            self.preview_list.addItem(path)

    def set_conversion_available(self, available: bool) -> None:
        self.compat_checkbox.setEnabled(available)
        self.compat_warning.setVisible(not available)


class ImportPage(QtWidgets.QWidget):
    start_requested = QtCore.Signal()
    cancel_requested = QtCore.Signal()

    def __init__(self, translator) -> None:
        super().__init__()
        self._tr = translator

        self.title = QtWidgets.QLabel()
        self.title.setObjectName('PageTitle')

        self.preview_label = QtWidgets.QLabel()
        self.preview_list = QtWidgets.QListWidget()
        self.preview_list.setMinimumHeight(140)

        self.start_btn = QtWidgets.QPushButton()
        self.start_btn.clicked.connect(self.start_requested.emit)
        self.cancel_btn = QtWidgets.QPushButton()
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        self.cancel_btn.setEnabled(False)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch(1)

        self.progress_label = QtWidgets.QLabel()
        self.progress_global = QtWidgets.QProgressBar()
        self.file_label = QtWidgets.QLabel()
        self.progress_file = QtWidgets.QProgressBar()

        self.log_label = QtWidgets.QLabel()
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(500)

        self.summary_group = QtWidgets.QGroupBox()
        summary_layout = QtWidgets.QGridLayout(self.summary_group)
        self.summary_copied = QtWidgets.QLabel()
        self.summary_skipped = QtWidgets.QLabel()
        self.summary_failed = QtWidgets.QLabel()
        self.summary_converted = QtWidgets.QLabel()

        summary_layout.addWidget(self.summary_copied, 0, 0)
        summary_layout.addWidget(self.summary_skipped, 0, 1)
        summary_layout.addWidget(self.summary_failed, 1, 0)
        summary_layout.addWidget(self.summary_converted, 1, 1)

        self.open_dest_btn = QtWidgets.QPushButton()
        self.open_log_btn = QtWidgets.QPushButton()
        self.open_dest_btn.setEnabled(False)
        self.open_log_btn.setEnabled(False)
        open_row = QtWidgets.QHBoxLayout()
        open_row.addWidget(self.open_dest_btn)
        open_row.addWidget(self.open_log_btn)
        open_row.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.title)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.preview_list)
        layout.addLayout(btn_row)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_global)
        layout.addWidget(self.file_label)
        layout.addWidget(self.progress_file)
        layout.addWidget(self.log_label)
        layout.addWidget(self.log_text, 1)
        layout.addWidget(self.summary_group)
        layout.addLayout(open_row)

        self.summary_group.setVisible(False)

    def retranslate(self) -> None:
        self.title.setText(self._tr.tr('step_import'))
        self.preview_label.setText(self._tr.tr('import_preview'))
        self.start_btn.setText(self._tr.tr('start_import'))
        self.cancel_btn.setText(self._tr.tr('cancel'))
        self.progress_label.setText(self._tr.tr('progress_global'))
        self.file_label.setText(self._tr.tr('progress_file'))
        self.log_label.setText(self._tr.tr('log_live'))
        self.summary_group.setTitle(self._tr.tr('summary_title'))
        self.open_dest_btn.setText(self._tr.tr('open_destination'))
        self.open_log_btn.setText(self._tr.tr('open_log'))
        if self._result is not None:
            self.set_result(self._result)

    def set_plan(self, plan: ImportPlan | None) -> None:
        self.preview_list.clear()
        if not plan:
            return
        for path in plan.preview_paths:
            self.preview_list.addItem(path)

    def set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)

    def append_log(self, line: str) -> None:
        self.log_text.appendPlainText(line)

    def reset_log(self) -> None:
        self.log_text.clear()

    def reset_progress(self) -> None:
        self.progress_global.setMaximum(1)
        self.progress_global.setValue(0)
        self.progress_file.setMaximum(1)
        self.progress_file.setValue(0)

    def set_progress(self, progress) -> None:
        scale = 1
        if progress.bytes_total > 2_000_000_000:
            scale = 1024 * 1024
        if progress.bytes_total > 0:
            self.progress_global.setMaximum(int(progress.bytes_total / scale))
            self.progress_global.setValue(int(progress.bytes_done / scale))
        if progress.current_total > 0:
            self.progress_file.setMaximum(int(progress.current_total / scale))
            self.progress_file.setValue(int(progress.current_bytes / scale))
        if progress.current_file:
            self.file_label.setText(f"{self._tr.tr('progress_file')}: {progress.current_file}")

    def set_result(self, result) -> None:
        self._result = result
        self.summary_copied.setText(f"{self._tr.tr('summary_copied')}: {result.copied}")
        self.summary_skipped.setText(f"{self._tr.tr('summary_skipped')}: {result.skipped}")
        self.summary_failed.setText(f"{self._tr.tr('summary_failed')}: {result.failed}")
        self.summary_converted.setText(f"{self._tr.tr('summary_converted')}: {result.converted}")
        self.summary_group.setVisible(True)
        self.open_dest_btn.setEnabled(True)
        self.open_log_btn.setEnabled(True)
