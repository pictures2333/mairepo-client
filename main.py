import sys
from pathlib import Path

import truststore
truststore.inject_into_ssl()
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src import frontend

# Assets

ICON_PATH = Path(__file__).resolve().parent / "icon.png"

# App


def main() -> int:
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    window = frontend.MairepoWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
