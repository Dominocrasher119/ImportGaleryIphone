from __future__ import annotations

from PySide6 import QtCore

from application.scan_device import scan_device
from application.execute_transfer import execute_transfer
from domain import CancelToken, DeviceInfo, ImportOptions, ImportPlan


class ScanWorker(QtCore.QThread):
    finished = QtCore.Signal(object)
    error = QtCore.Signal(str)

    def __init__(self, device: DeviceInfo) -> None:
        super().__init__()
        self._device = device

    def run(self) -> None:
        try:
            result = scan_device(self._device)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class TransferWorker(QtCore.QThread):
    progress = QtCore.Signal(object)
    log = QtCore.Signal(str)
    finished = QtCore.Signal(object)
    error = QtCore.Signal(str)

    def __init__(
        self,
        plan: ImportPlan,
        device: DeviceInfo,
        options: ImportOptions,
        cancel_token: CancelToken,
    ) -> None:
        super().__init__()
        self._plan = plan
        self._device = device
        self._options = options
        self._cancel_token = cancel_token

    def run(self) -> None:
        try:
            result = execute_transfer(
                self._plan,
                self._device,
                self._options,
                self.progress.emit,
                self.log.emit,
                self._cancel_token,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))