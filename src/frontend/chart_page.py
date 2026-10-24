from collections.abc import Callable
from functools import partial
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src import backend, schema
from .chart_list import ChartList
from .worker import BackendWorker


class ChartPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._worker: Optional[BackendWorker] = None
        self._charts: list[schema.Chart] = []
        self._subscribed_chart_ids: set[int] = set()
        self._active_search = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Mairepo client")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        self._connection_info = QLabel()
        self._connection_info.setWordWrap(True)
        layout.addWidget(self._connection_info)

        controls = QHBoxLayout()
        self._filter_box = QComboBox()
        self._filter_box.addItems(("All charts", "Subscribed", "Unsubscribed"))
        self._filter_box.currentIndexChanged.connect(self._render_charts)
        self._search_entry = QLineEdit()
        self._search_entry.setPlaceholderText("Search charts")
        self._search_entry.returnPressed.connect(self._search)
        self._search_button = QPushButton("Search")
        self._search_button.clicked.connect(self._search)
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.clicked.connect(self._refresh)
        self._sync_button = QPushButton("Sync")
        self._sync_button.setEnabled(False)
        self._sync_button.setToolTip("Sync is not available yet.")
        controls.addWidget(self._filter_box)
        controls.addWidget(self._search_entry, 1)
        controls.addWidget(self._search_button)
        controls.addWidget(self._refresh_button)
        controls.addWidget(self._sync_button)
        layout.addLayout(controls)

        self._status = QLabel()
        layout.addWidget(self._status)

        self._chart_list = ChartList()
        self._chart_list.subscription_changed.connect(self._set_subscription)
        layout.addWidget(self._chart_list, 1)

    def load(self) -> None:
        storage_directory = backend.get_storage_directory()
        if storage_directory is None:
            return

        self._charts = backend.get_charts()
        self._subscribed_chart_ids = backend.get_subscribed_chart_ids()
        self._connection_info.setText(
            f"URL: {backend.get_server_url()}\n"
            f"Storage directory: {storage_directory}"
        )
        self._render_charts()

    def is_busy(self) -> bool:
        return self._worker is not None

    def _search(self) -> None:
        self._active_search = self._search_entry.text().strip().casefold()
        self._render_charts()

    def _refresh(self) -> None:
        self._start_operation(backend.refresh, "Refreshing remote index...")

    def _set_subscription(self, chart_id: int, subscribed: bool) -> None:
        self._start_operation(
            partial(backend.set_subscription, chart_id, subscribed),
            "Updating subscription...",
        )

    def _start_operation(
        self,
        operation: Callable[[], None],
        status: str,
    ) -> None:
        if self._worker is not None:
            return

        self._set_busy(True, status)
        worker = BackendWorker(operation)
        worker.finished.connect(self._operation_finished)
        self._worker = worker
        worker.start()

    def _operation_finished(self) -> None:
        worker = self.sender()
        if worker is not self._worker or not isinstance(worker, BackendWorker):
            return

        self._worker = None
        error = worker.error
        worker.deleteLater()
        self.load()
        self._set_busy(False)

        if error is not None:
            QMessageBox.critical(self, "Backend operation failed", error)

    def _set_busy(self, busy: bool, status: str = "") -> None:
        self._filter_box.setEnabled(not busy)
        self._search_entry.setEnabled(not busy)
        self._search_button.setEnabled(not busy)
        self._refresh_button.setEnabled(not busy)
        self._chart_list.setEnabled(not busy)
        if status:
            self._status.setText(status)

    def _render_charts(self) -> None:
        filter_value = self._filter_box.currentText()
        visible_charts = []
        for chart in self._charts:
            subscribed = chart.id in self._subscribed_chart_ids
            if filter_value == "Subscribed" and not subscribed:
                continue
            if filter_value == "Unsubscribed" and subscribed:
                continue
            if self._active_search not in chart.name.casefold():
                continue
            visible_charts.append(chart)

        self._chart_list.show_charts(
            visible_charts,
            self._subscribed_chart_ids,
        )
        self._status.setText(
            f"{len(visible_charts)} of {len(self._charts)} charts | "
            f"{len(self._subscribed_chart_ids)} subscribed"
        )
