from functools import partial
from typing import Optional
from uuid import UUID

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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from pydantic import ValidationError

from src import backend, schema
from . import saved_connections
from .worker import OperationWorker

# Connection page


class ConnectionPage(QWidget):
    connected = Signal()

    def __init__(self) -> None:
        super().__init__()

        # State
        self._worker: Optional[OperationWorker] = None
        self._saved_connections: list[schema.SavedConnection] = []
        self._saved_connections_available = False

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

        # Saved connections
        self._saved_group = QGroupBox("Saved connections")
        self._saved_group.setEnabled(False)
        saved_group_layout = QVBoxLayout(self._saved_group)
        saved_scroll = QScrollArea()
        saved_scroll.setWidgetResizable(True)
        saved_container = QWidget()
        self._saved_layout = QVBoxLayout(saved_container)
        saved_scroll.setWidget(saved_container)
        saved_group_layout.addWidget(saved_scroll)
        layout.addWidget(self._saved_group, 1)

        self._load_saved_connections()

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

        # Offer to persist settings only when the feature loaded successfully
        if self._saved_connections_available:
            save = QMessageBox.question(
                self,
                "Save connection",
                "Save this connection to Saved connections?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if save == QMessageBox.StandardButton.Yes:
                try:
                    connections = saved_connections.add(settings)
                except Exception as error:
                    message = (
                        str(error)
                        if isinstance(error, RuntimeError)
                        else "An unexpected saved connection error occurred."
                    )
                    QMessageBox.warning(
                        self,
                        "Could not save connection",
                        f"{message}\n\n"
                        "The connection will continue without saving.",
                    )
                else:
                    self._saved_connections = connections
                    self._render_saved_connections()

        self._start_connection(settings)

    def _connect_saved(self, connection_id: UUID) -> None:
        if self._worker is not None or not self._saved_connections_available:
            return

        # Resolve the selected in-memory entry
        connection = next(
            (
                item
                for item in self._saved_connections
                if item.id == connection_id
            ),
            None,
        )
        if connection is None:
            QMessageBox.critical(
                self,
                "Saved connection unavailable",
                "The selected saved connection is no longer available.",
            )
            return

        # Populate the form and validate the current filesystem state
        self._storage_entry.setText(str(connection.storage_directory))
        self._server_entry.setText(str(connection.server_url).rstrip("/"))
        self._token_entry.setText(connection.token)
        try:
            settings = schema.ConnectionSettings(
                storage_directory=connection.storage_directory,
                server_url=connection.server_url,
                token=connection.token,
            )
        except ValidationError as error:
            QMessageBox.critical(
                self,
                "Invalid saved connection",
                self._format_validation_error(error),
            )
            return

        self._start_connection(settings)

    def _start_connection(self, settings: schema.ConnectionSettings) -> None:
        # Start the backend operation
        self._set_busy(True)
        worker = OperationWorker(partial(backend.connect, settings))
        worker.finished.connect(self._connection_finished)
        self._worker = worker
        worker.start()

    def _connection_finished(self) -> None:
        worker = self.sender()
        if worker is not self._worker or not isinstance(worker, OperationWorker):
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

        # Continue to the chart page after local initialization
        self.connected.emit()

    # UI state

    def _set_busy(self, busy: bool) -> None:
        self._storage_entry.setEnabled(not busy)
        self._server_entry.setEnabled(not busy)
        self._token_entry.setEnabled(not busy)
        self._browse_button.setEnabled(not busy)
        self._connect_button.setEnabled(not busy)
        self._saved_group.setEnabled(
            self._saved_connections_available and not busy
        )
        self._status.setText("Connecting..." if busy else "Not connected")

    # Saved connections

    def _load_saved_connections(self) -> None:
        self._saved_connections_available = False
        self._saved_group.setEnabled(False)
        try:
            connections = saved_connections.load()
        except Exception:
            self._saved_connections = []
        else:
            self._saved_connections = connections
            self._saved_connections_available = True
        self._render_saved_connections()
        self._saved_group.setEnabled(self._saved_connections_available)

    def _delete_saved_connection(self, connection_id: UUID) -> None:
        if not self._saved_connections_available:
            return

        try:
            self._saved_connections = saved_connections.delete(connection_id)
        except Exception as error:
            message = (
                str(error)
                if isinstance(error, RuntimeError)
                else "An unexpected saved connection error occurred."
            )
            QMessageBox.warning(
                self,
                "Could not delete connection",
                message,
            )
            return
        self._render_saved_connections()

    def _render_saved_connections(self) -> None:
        while self._saved_layout.count():
            item = self._saved_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self._saved_connections_available:
            self._saved_layout.addWidget(QLabel("Saved connections unavailable."))
            self._saved_layout.addStretch()
            return

        if not self._saved_connections:
            self._saved_layout.addWidget(QLabel("No saved connections."))
            self._saved_layout.addStretch()
            return

        for connection in self._saved_connections:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            details = QVBoxLayout()
            details.addWidget(
                QLabel(str(connection.server_url).rstrip("/"))
            )
            storage = QLabel(str(connection.storage_directory))
            storage.setWordWrap(True)
            details.addWidget(storage)

            connect_button = QPushButton("Connect")
            connect_button.clicked.connect(
                partial(self._connect_saved, connection.id)
            )
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(
                partial(self._delete_saved_connection, connection.id)
            )
            row_layout.addLayout(details, 1)
            row_layout.addWidget(connect_button)
            row_layout.addWidget(delete_button)
            self._saved_layout.addWidget(row)
        self._saved_layout.addStretch()

    # Helpers

    @staticmethod
    def _format_validation_error(error: ValidationError) -> str:
        messages = []
        for item in error.errors(include_url=False, include_context=False):
            field = str(item["loc"][0]) if item["loc"] else "input"
            messages.append(f"{field}: {item['msg']}")
        return "\n".join(messages)
