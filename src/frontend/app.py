from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from src import backend
from .chart_page import ChartPage
from .connection_page import ConnectionPage

# Window


class MairepoWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        # Window
        self.setWindowTitle("mairepo client")
        self.resize(980, 680)
        self.setMinimumSize(760, 520)

        # Pages
        self._connection_page = ConnectionPage()
        self._chart_page = ChartPage()

        self._pages = QStackedWidget()
        self._pages.addWidget(self._connection_page)
        self._pages.addWidget(self._chart_page)
        self.setCentralWidget(self._pages)

        # Navigation
        self._connection_page.connected.connect(self._show_chart_page)

    # Navigation

    def _show_chart_page(self) -> None:
        self._chart_page.load()
        self._pages.setCurrentWidget(self._chart_page)

    # Lifecycle

    def closeEvent(self, event: QCloseEvent) -> None:
        # Keep workers alive until their backend operation settles
        if self._connection_page.is_busy() or self._chart_page.is_busy():
            QMessageBox.information(
                self,
                "Operation in progress",
                "Wait for the current operation to finish before closing.",
            )
            event.ignore()
            return

        # Release the backend before accepting the close event
        try:
            backend.close()
        except RuntimeError as error:
            QMessageBox.critical(self, "Could not close backend", str(error))
            event.ignore()
            return
        event.accept()
