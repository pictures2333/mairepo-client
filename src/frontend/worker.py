from collections.abc import Callable
from typing import Optional

from PySide6.QtCore import QThread, Signal

from src import schema

# Operation worker


class OperationWorker(QThread):
    def __init__(self, operation: Callable[[], None]) -> None:
        super().__init__()
        self._operation = operation
        self.error: Optional[str] = None

    def run(self) -> None:
        # Convert backend failures into a GUI-readable result
        try:
            self._operation()
        except RuntimeError as error:
            self.error = str(error)
        except Exception:
            self.error = "An unexpected backend error occurred."


# Chart state worker


class ChartStateWorker(QThread):
    def __init__(
        self,
        operation: Callable[[], list[schema.ChartState]],
    ) -> None:
        super().__init__()
        self._operation = operation
        self.charts: Optional[list[schema.ChartState]] = None
        self.error: Optional[str] = None

    def run(self) -> None:
        # Convert backend failures into a GUI-readable result
        try:
            self.charts = self._operation()
        except RuntimeError as error:
            self.error = str(error)
        except Exception:
            self.error = "An unexpected backend error occurred."


class SyncWorker(QThread):
    progress_changed = Signal(int, int)

    def __init__(
        self,
        operation: Callable[
            [Callable[[int, int], None]],
            schema.SyncReport,
        ],
    ) -> None:
        super().__init__()
        self._operation = operation
        self.report: Optional[schema.SyncReport] = None
        self.error: Optional[str] = None

    def run(self) -> None:
        # Forward backend progress and preserve the final report
        try:
            self.report = self._operation(self.progress_changed.emit)
        except RuntimeError as error:
            self.error = str(error)
        except Exception:
            self.error = "An unexpected backend error occurred."
