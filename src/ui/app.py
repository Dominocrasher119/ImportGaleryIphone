from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from application.build_plan import build_plan
from application.detect_devices import detect_iphone_devices
from application.convert_media import conversion_available
from domain import CancelToken, DeviceInfo, ImportOptions
from infrastructure.fs.config_store import load_config, save_config
from infrastructure.fs.path_utils import get_app_root
from ui.translator import Translator, detect_system_language
from ui.wizard import DevicePage, ImportPage, OptionsPage, ScanPage, StepIndicator
from ui.workers import ScanWorker, TransferWorker


class WizardWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._app_root = get_app_root()
        self._translator = Translator()
        self._config = load_config(self._app_root)
        self._scan_worker: ScanWorker | None = None
        self._transfer_worker: TransferWorker | None = None
        self._cancel_token: CancelToken | None = None
        self._scan_cancel_token: CancelToken | None = None
        self._devices: list[DeviceInfo] = []
        self._selected_device: DeviceInfo | None = None
        self._scan_result = None
        self._plan = None
        self._import_running = False
        self._last_log_path: Path | None = None
        self._last_dest: Path | None = None

        self._apply_language_from_config()
        self._build_ui()
        self._apply_config_to_ui()
        self._connect_signals()
        self.refresh_devices()

    def _apply_language_from_config(self) -> None:
        lang = self._config.get('language') or detect_system_language()
        self._translator.set_language(lang)

    def _build_ui(self) -> None:
        self.setWindowTitle('iImport')
        self.setObjectName('MainWindow')
        self.resize(980, 720)

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 18)
        layout.setSpacing(18)

        header = QtWidgets.QHBoxLayout()
        title_col = QtWidgets.QVBoxLayout()
        self.title_label = QtWidgets.QLabel()
        self.title_label.setObjectName('AppTitle')
        self.subtitle_label = QtWidgets.QLabel()
        self.subtitle_label.setObjectName('AppSubtitle')
        title_col.addWidget(self.title_label)
        title_col.addWidget(self.subtitle_label)
        header.addLayout(title_col)
        header.addStretch(1)

        self.lang_combo = QtWidgets.QComboBox()
        self.lang_combo.addItem('Español', 'es')
        self.lang_combo.addItem('English', 'en')
        self.lang_combo.addItem('Català', 'ca')
        header.addWidget(self.lang_combo)

        self.step_indicator = StepIndicator(self._translator)

        self.stack = QtWidgets.QStackedWidget()
        self.device_page = DevicePage(self._translator)
        self.scan_page = ScanPage(self._translator)
        self.options_page = OptionsPage(self._translator)
        self.import_page = ImportPage(self._translator)
        self.stack.addWidget(self.device_page)
        self.stack.addWidget(self.scan_page)
        self.stack.addWidget(self.options_page)
        self.stack.addWidget(self.import_page)

        nav = QtWidgets.QHBoxLayout()
        self.back_btn = QtWidgets.QPushButton()
        self.next_btn = QtWidgets.QPushButton()
        self.cancel_btn = QtWidgets.QPushButton()
        self.cancel_btn.setObjectName('Secondary')
        nav.addWidget(self.back_btn)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        nav.addWidget(self.cancel_btn)

        layout.addLayout(header)
        layout.addWidget(self.step_indicator)
        layout.addWidget(self.stack, 1)
        layout.addLayout(nav)

        self.setCentralWidget(central)
        self._retranslate()
        self._set_step(0)

    def _connect_signals(self) -> None:
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        self.back_btn.clicked.connect(self._on_back)
        self.next_btn.clicked.connect(self._on_next)
        self.cancel_btn.clicked.connect(self.close)

        self.device_page.refresh_requested.connect(self.refresh_devices)
        self.device_page.device_selected.connect(self._on_device_selected)

        self.scan_page.scan_requested.connect(self._start_scan)
        self.scan_page.cancel_requested.connect(self._cancel_scan)

        self.options_page.browse_requested.connect(self._browse_destination)
        self.options_page.options_changed.connect(self._on_options_changed)

        self.import_page.start_requested.connect(self._start_import)
        self.import_page.cancel_requested.connect(self._cancel_import)
        self.import_page.open_dest_btn.clicked.connect(self._open_destination)
        self.import_page.open_log_btn.clicked.connect(self._open_log)

        self._translator.language_changed.connect(self._retranslate)

    def _apply_config_to_ui(self) -> None:
        lang = self._translator.language()
        idx = self.lang_combo.findData(lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

        preset = self._config.get('structure_preset', 'A')
        preset_idx = self.options_page.preset_combo.findData(preset)
        if preset_idx >= 0:
            self.options_page.preset_combo.setCurrentIndex(preset_idx)

        self.options_page.template_edit.setText(self._config.get('template', '{YYYY}/{MM}/'))
        self.options_page.dest_edit.setText(self._config.get('last_destination', ''))
        self.options_page.compat_checkbox.setChecked(bool(self._config.get('create_compat', False)))
        self.options_page.live_checkbox.setChecked(bool(self._config.get('keep_live', True)))

        self._update_conversion_availability()

    def _save_config_from_ui(self) -> None:
        data = {
            'language': self._translator.language(),
            'structure_preset': self.options_page.preset(),
            'template': self.options_page.template(),
            'last_destination': self.options_page.destination(),
            'keep_live': self.options_page.live_checkbox.isChecked(),
            'create_compat': self.options_page.compat_checkbox.isChecked(),
        }
        save_config(self._app_root, data)

    def _retranslate(self) -> None:
        self.title_label.setText(self._translator.tr('app_title'))
        self.subtitle_label.setText(self._translator.tr('wizard_subtitle'))
        self.step_indicator.set_steps([
            self._translator.tr('step_device'),
            self._translator.tr('step_scan'),
            self._translator.tr('step_options'),
            self._translator.tr('step_import'),
        ])
        self.back_btn.setText(self._translator.tr('back'))
        self.next_btn.setText(self._translator.tr('next'))
        self.cancel_btn.setText(self._translator.tr('cancel'))
        self.device_page.retranslate()
        self.device_page.set_devices(self._devices)
        self.scan_page.retranslate()
        self.options_page.retranslate()
        self.import_page.retranslate()
        self._update_nav_buttons()
        self._update_preview()

    def _set_step(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.step_indicator.set_current(index)
        self._animate_page(self.stack.currentWidget())
        self._update_nav_buttons()

    def _animate_page(self, widget: QtWidgets.QWidget) -> None:
        effect = QtWidgets.QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QtCore.QPropertyAnimation(effect, b'opacity', widget)
        anim.setDuration(240)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def _update_nav_buttons(self) -> None:
        step = self.stack.currentIndex()
        self.back_btn.setEnabled(step > 0 and not self._import_running)

        if step < 3:
            self.next_btn.setText(self._translator.tr('next'))
            self.next_btn.setEnabled(self._is_step_complete(step) and not self._import_running)
        else:
            self.next_btn.setText(self._translator.tr('close'))
            self.next_btn.setEnabled(not self._import_running)

    def _is_step_complete(self, step: int) -> bool:
        if step == 0:
            return self._selected_device is not None
        if step == 1:
            return self._scan_result is not None
        if step == 2:
            return bool(self.options_page.destination().strip()) and self._scan_result is not None
        return True

    def refresh_devices(self) -> None:
        try:
            devices = detect_iphone_devices()
        except Exception:
            # COM error or other WPD issue - show empty list
            devices = []
        self._devices = devices
        self.device_page.set_devices(self._devices)

    def _on_device_selected(self, device: DeviceInfo) -> None:
        self._selected_device = device
        self._scan_result = None
        self.scan_page.set_scan_result(None)
        self._update_nav_buttons()

    def _start_scan(self) -> None:
        if not self._selected_device or self._scan_worker:
            return
        self.scan_page.set_scanning(True)
        self.scan_page.scan_btn.setEnabled(False)
        self._scan_cancel_token = CancelToken()
        self._scan_worker = ScanWorker(self._selected_device, self._scan_cancel_token)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.items_found.connect(self.scan_page.add_scan_items)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.cancelled.connect(self._on_scan_cancelled)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _cancel_scan(self) -> None:
        if self._scan_cancel_token:
            self._scan_cancel_token.cancel()

    def _on_scan_progress(self, done: int, total: int, path: str) -> None:
        self.scan_page.set_scan_progress(done, total, path)

    def _on_scan_finished(self, result) -> None:
        self._scan_worker = None
        self._scan_cancel_token = None
        self._scan_result = result
        self.scan_page.set_scanning(False)
        self.scan_page.scan_btn.setEnabled(True)
        self.scan_page.set_scan_result(result)
        self._update_preview()
        self._update_nav_buttons()

    def _on_scan_cancelled(self) -> None:
        self._scan_worker = None
        self._scan_cancel_token = None
        self._scan_result = None
        self.scan_page.set_scanning(False)
        self.scan_page.scan_btn.setEnabled(True)
        self.scan_page.set_scan_cancelled()
        self.scan_page.set_scan_result(None)
        self._update_nav_buttons()

    def _on_scan_error(self, message: str) -> None:
        self._scan_worker = None
        self._scan_cancel_token = None
        self.scan_page.set_scanning(False)
        self.scan_page.scan_btn.setEnabled(True)
        QtWidgets.QMessageBox.warning(self, 'iImport', self._translate_error(message, 'error_scan_failed'))

    def _browse_destination(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, self._translator.tr('destination_label'))
        if path:
            self.options_page.set_destination(path)
            self._update_preview()

    def _on_options_changed(self) -> None:
        self._update_preview()
        self._update_nav_buttons()

    def _update_preview(self) -> None:
        if not self._scan_result or not self._selected_device:
            return
        dest = self.options_page.destination().strip() or '.'
        options = self._build_options(Path(dest))
        sample_items = self._scan_result.items[:200]
        preview_plan = build_plan(self._selected_device, sample_items, options)
        self.options_page.set_preview(preview_plan.preview_paths)

    def _build_options(self, destination: Path) -> ImportOptions:
        preset = self.options_page.preset()
        template = self.options_page.template()
        if self.options_page.use_advanced():
            preset = 'ADV'
        create_compat = self.options_page.compat_checkbox.isChecked()
        if not conversion_available(self._app_root):
            create_compat = False
        return ImportOptions(
            destination=destination,
            structure_preset=preset,
            template=template,
            keep_live=self.options_page.live_checkbox.isChecked(),
            create_compat=create_compat,
            language=self._translator.language(),
        )

    def _on_back(self) -> None:
        step = self.stack.currentIndex()
        if step > 0:
            self._set_step(step - 1)

    def _on_next(self) -> None:
        step = self.stack.currentIndex()
        if step < 3:
            if step == 2:
                self._prepare_import_step()
            self._set_step(step + 1)
        else:
            self.close()

    def _prepare_import_step(self) -> None:
        if not self._scan_result or not self._selected_device:
            return
        dest = Path(self.options_page.destination().strip())
        options = self._build_options(dest)
        self._plan = build_plan(self._selected_device, self._scan_result.items, options)
        self.import_page.set_plan(self._plan)
        self.import_page.summary_group.setVisible(False)
        self.import_page.reset_log()
        self.import_page.reset_progress()
        self.import_page.start_btn.setEnabled(self._plan.total_files > 0)

    def _start_import(self) -> None:
        if not self._plan or not self._selected_device or self._transfer_worker:
            return
        dest = Path(self.options_page.destination().strip())
        if not dest:
            return
        options = self._build_options(dest)
        self._cancel_token = CancelToken()
        self._import_running = True
        self.import_page.set_running(True)
        self.import_page.reset_log()
        self.import_page.reset_progress()
        self._update_nav_buttons()

        self._transfer_worker = TransferWorker(self._plan, self._selected_device, options, self._cancel_token)
        self._transfer_worker.progress.connect(self.import_page.set_progress)
        self._transfer_worker.log.connect(self.import_page.append_log)
        self._transfer_worker.finished.connect(self._on_import_finished)
        self._transfer_worker.error.connect(self._on_import_error)
        self._transfer_worker.start()

    def _cancel_import(self) -> None:
        if self._cancel_token:
            self._cancel_token.cancel()

    def _on_import_finished(self, result) -> None:
        self._transfer_worker = None
        self._import_running = False
        self.import_page.set_running(False)
        self.import_page.set_result(result)
        self._last_log_path = result.log_path
        self._last_dest = Path(self.options_page.destination().strip())
        self._update_nav_buttons()

    def _on_import_error(self, message: str) -> None:
        self._transfer_worker = None
        self._import_running = False
        self.import_page.set_running(False)
        self._update_nav_buttons()
        QtWidgets.QMessageBox.warning(self, 'iImport', self._translate_error(message, 'error_import_failed'))

    def _translate_error(self, message: str, fallback_key: str) -> str:
        if message:
            translated = self._translator.tr(message)
            if translated != message:
                return translated
        return self._translator.tr(fallback_key)

    def _on_language_changed(self) -> None:
        code = self.lang_combo.currentData()
        if code:
            self._translator.set_language(code)
            self._save_config_from_ui()

    def _update_conversion_availability(self) -> None:
        available = conversion_available(self._app_root)
        if not available:
            self.options_page.compat_checkbox.setChecked(False)
        self.options_page.set_conversion_available(available)

    def _open_destination(self) -> None:
        if not self._last_dest:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self._last_dest)))

    def _open_log(self) -> None:
        if not self._last_log_path:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self._last_log_path)))

    def closeEvent(self, event) -> None:
        self._save_config_from_ui()
        super().closeEvent(event)
