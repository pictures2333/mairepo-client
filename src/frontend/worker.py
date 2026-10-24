from collections.abc import Callable
from typing import Optional

from PySide6.QtCore import QThread

# Backend worker


class BackendWorker(QThread):
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
