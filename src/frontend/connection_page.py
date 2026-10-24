from functools import partial
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from pydantic import ValidationError

from src import backend, schema
from .worker import BackendWorker

# Connection page


class ConnectionPage(QWidget):
    connected = Signal()

    def __init__(self) -> None:
        super().__init__()

        # State
        self._worker: Optional[BackendWorker] = None

        # Header
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Mairepo client")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        layout.addWidget(QLabel("Connect to server"))

        # Connection form
        group = QGroupBox("Connection")
        form = QFormLayout(group)

        storage_row = QWidget()
        storage_layout = QHBoxLayout(storage_row)
        storage_layout.setContentsMargins(0, 0, 0, 0)
        self._storage_entry = QLineEdit()
        self._browse_button = QPushButton("Browse")
        self._browse_button.clicked.connect(self._choose_storage_directory)
        storage_layout.addWidget(self._storage_entry, 1)
        storage_layout.addWidget(self._browse_button)
        form.addRow("Storage directory", storage_row)

        self._server_entry = QLineEdit()
        form.addRow("Server URL", self._server_entry)

        self._token_entry = QLineEdit()
        self._token_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_entry.returnPressed.connect(self._connect)
        form.addRow("Token", self._token_entry)

        # Actions
        action_row = QWidget()
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        self._status = QLabel("Not connected")
        self._connect_button = QPushButton("Connect")
        self._connect_button.clicked.connect(self._connect)
        action_layout.addWidget(self._status, 1)
        action_layout.addWidget(self._connect_button)
        form.addRow(action_row)

        layout.addWidget(group)
        layout.addStretch()

    # State

    def is_busy(self) -> bool:
        return self._worker is not None

    # Input

    def _choose_storage_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select the AstroDX levels directory",
        )
        if directory:
            self._storage_entry.setText(directory)

    # Connection

    def _connect(self) -> None:
        if self._worker is not None:
            return

        # Validate input before starting background work
        try:
            settings = schema.ConnectionSettings(
                storage_directory=self._storage_entry.text(),
                server_url=self._server_entry.text(),
                token=self._token_entry.text(),
            )
        except ValidationError as error:
            QMessageBox.critical(
                self,
                "Invalid input",
                self._format_validation_error(error),
            )
            return

        # Start the backend operation
        self._set_busy(True)
        worker = BackendWorker(partial(backend.connect, settings))
        worker.finished.connect(self._connection_finished)
        self._worker = worker
        worker.start()

    def _connection_finished(self) -> None:
        worker = self.sender()
        if worker is not self._worker or not isinstance(worker, BackendWorker):
            return

        # Detach the completed worker
        self._worker = None
        error = worker.error
        worker.deleteLater()

        # Restore the form after a failed connection
        if error is not None:
            self._set_busy(False)
            QMessageBox.critical(self, "Connection failed", error)
            return

        # Let the window switch pages immediately on success
        self.connected.emit()

    # UI state

    def _set_busy(self, busy: bool) -> None:
        self._storage_entry.setEnabled(not busy)
        self._server_entry.setEnabled(not busy)
        self._token_entry.setEnabled(not busy)
        self._browse_button.setEnabled(not busy)
        self._connect_button.setEnabled(not busy)
        self._status.setText("Connecting..." if busy else "Not connected")

    # Helpers

    @staticmethod
    def _format_validation_error(error: ValidationError) -> str:
        messages = []
        for item in error.errors(include_url=False, include_context=False):
            field = str(item["loc"][0]) if item["loc"] else "input"
            messages.append(f"{field}: {item['msg']}")
        return "\n".join(messages)
