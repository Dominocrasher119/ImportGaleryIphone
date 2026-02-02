from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtWidgets

from infrastructure.fs.path_utils import resource_path
from ui.app import WizardWindow


def _load_style(app: QtWidgets.QApplication) -> None:
    style_path = resource_path('ui/resources/style.qss', 'src/ui/resources/style.qss')
    try:
        app.setStyleSheet(style_path.read_text(encoding='utf-8'))
    except Exception:
        pass


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('iImport')
    _load_style(app)
    window = WizardWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())