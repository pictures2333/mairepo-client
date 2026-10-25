from collections.abc import Callable
from functools import partial
from typing import Optional

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src import backend, schema
from .chart_list import ChartList
from .worker import ChartStateWorker, OperationWorker, SyncWorker

# Chart page


class ChartPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        # State
        self._worker: Optional[QThread] = None
        self._charts: list[schema.ChartState] = []
        self._active_search = ""
        self._pending_sync_report: Optional[schema.SyncReport] = None

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

        self._connection_info = QLabel()
        self._connection_info.setWordWrap(True)
        layout.addWidget(self._connection_info)

        # Repository summary
        self._summary = QLabel()
        layout.addWidget(self._summary)

        # Search and actions
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
        self._sync_button.clicked.connect(self._sync)
        controls.addWidget(self._filter_box)
        controls.addWidget(self._search_entry, 1)
        controls.addWidget(self._search_button)
        controls.addWidget(self._refresh_button)
        controls.addWidget(self._sync_button)
        layout.addLayout(controls)

        # Sync progress
        self._sync_progress = QProgressBar()
        self._sync_progress.hide()
        layout.addWidget(self._sync_progress)

        # Chart results
        self._status = QLabel()
        layout.addWidget(self._status)

        self._chart_list = ChartList()
        self._chart_list.subscription_requested.connect(self._set_subscription)
        layout.addWidget(self._chart_list, 1)

        # Wait for the first remote snapshot after local initialization
        self._set_busy(True, "Loading charts...")

    # Data

    def load(self) -> None:
        if self._worker is not None:
            return

        # Keep the page frozen until a complete snapshot is rendered
        self._set_busy(True, "Loading charts...")
        worker = ChartStateWorker(backend.refresh)
        worker.finished.connect(self._load_finished)
        self._worker = worker
        worker.start()

    def _display_charts(self, charts: list[schema.ChartState]) -> bool:
        try:
            # Apply the frontend-owned display snapshot
            storage_directory = backend.get_storage_directory()
            if storage_directory is None:
                raise RuntimeError("The backend connection is unavailable.")
            self._charts = list(charts)

            # Refresh connection details and repository summary
            self._connection_info.setText(
                f"URL: {backend.get_server_url()}\n"
                f"Storage directory: {storage_directory}"
            )
            subscribed = sum(chart.subscribed for chart in self._charts)
            outdated = sum(
                chart.subscribed and chart.outdated
                for chart in self._charts
            )
            up_to_date = sum(
                chart.subscribed and not chart.outdated and not chart.missing
                for chart in self._charts
            )
            missing = sum(
                chart.subscribed and chart.missing
                for chart in self._charts
            )
            self._summary.setText(
                f"{subscribed} subscribed | {outdated} outdated | "
                f"{up_to_date} up to date | {missing} missing"
            )
            self._render_charts()
        except Exception as error:
            # Freeze an unusable page until the application is restarted
            self._set_busy(True, "Chart display failed. Restart the application.")
            QMessageBox.critical(
                self,
                "Could not display charts",
                f"{error}\n\nRestart the application to continue.",
            )
            return False

        return True

    def is_busy(self) -> bool:
        return self._worker is not None

    # Actions

    def _search(self) -> None:
        self._active_search = self._search_entry.text().strip().casefold()
        self._render_charts()

    def _refresh(self) -> None:
        if self._worker is not None:
            return
        self._set_busy(True, "Refreshing remote index...")
        self.load()

    def _set_subscription(
        self,
        chart_id: int,
        target_subscribed: bool,
    ) -> None:
        self._start_operation(
            partial(backend.set_subscription, chart_id, target_subscribed),
            "Updating subscription...",
        )

    def _sync(self) -> None:
        if self._worker is not None:
            return

        # Compare first, then switch to determinate chart progress
        self._set_busy(True, "Comparing local and remote charts...")
        self._sync_progress.setRange(0, 0)
        self._sync_progress.show()

        worker = SyncWorker(backend.sync)
        worker.progress_changed.connect(self._sync_progress_changed)
        worker.finished.connect(self._sync_finished)
        self._worker = worker
        worker.start()

    # Worker lifecycle

    def _start_operation(
        self,
        operation: Callable[[], None],
        status: str,
    ) -> None:
        if self._worker is not None:
            return

        # Lock the page while one backend operation is active
        self._set_busy(True, status)

        # Start the operation in a background thread
        worker = OperationWorker(operation)
        worker.finished.connect(self._operation_finished)
        self._worker = worker
        worker.start()

    def _load_finished(self) -> None:
        worker = self.sender()
        if worker is not self._worker or not isinstance(worker, ChartStateWorker):
            return

        # Detach the completed loader
        self._worker = None
        charts = worker.charts
        error = worker.error
        worker.deleteLater()

        if error is not None or charts is None:
            self._pending_sync_report = None
            self._set_busy(True, "Chart loading failed. Restart the application.")
            QMessageBox.critical(
                self,
                "Could not load charts",
                f"{error or 'The backend did not return chart data.'}\n\n"
                "Restart the application to continue.",
            )
            return

        # Only a successfully rendered snapshot may unlock the page
        if not self._display_charts(charts):
            self._pending_sync_report = None
            return
        self._set_busy(False)

        if self._pending_sync_report is not None:
            report = self._pending_sync_report
            self._pending_sync_report = None
            self._show_sync_report(report)

    def _operation_finished(self) -> None:
        worker = self.sender()
        if worker is not self._worker or not isinstance(worker, OperationWorker):
            return

        # Detach the completed worker
        self._worker = None
        error = worker.error
        worker.deleteLater()

        if error is not None:
            # Keep a failed page frozen instead of loading another snapshot
            self._set_busy(
                True,
                f"Backend operation failed: {error} Restart the application.",
            )
            QMessageBox.critical(
                self,
                "Backend operation failed",
                f"{error}\n\nRestart the application to continue.",
            )
            return

        # Reload authoritative display state before unlocking the page
        self.load()

    def _sync_progress_changed(self, completed: int, total: int) -> None:
        self._sync_progress.setRange(0, max(total, 1))
        self._sync_progress.setValue(completed)
        self._status.setText(f"Syncing charts... {completed} of {total}")

    def _sync_finished(self) -> None:
        worker = self.sender()
        if worker is not self._worker or not isinstance(worker, SyncWorker):
            return

        # Detach the completed worker and hide sync-only progress
        self._worker = None
        report = worker.report
        error = worker.error
        worker.deleteLater()
        self._sync_progress.hide()

        if error is not None or report is None:
            failure = error or "The backend did not return a sync report."
            self._pending_sync_report = None
            self._set_busy(
                True,
                f"Sync failed: {failure} Restart the application.",
            )
            QMessageBox.critical(
                self,
                "Sync failed",
                f"{failure}\n\nRestart the application to continue.",
            )
            return

        self._pending_sync_report = report

        # Reload authoritative display state before unlocking the page
        self.load()

    # UI state

    def _set_busy(self, busy: bool, status: str = "") -> None:
        self._filter_box.setEnabled(not busy)
        self._search_entry.setEnabled(not busy)
        self._search_button.setEnabled(not busy)
        self._refresh_button.setEnabled(not busy)
        self._sync_button.setEnabled(not busy)
        self._chart_list.setEnabled(not busy)
        if status:
            self._status.setText(status)

    # Filtering

    def _render_charts(self) -> None:
        # Apply the selected subscription and text filters
        filter_value = self._filter_box.currentText()
        visible_charts = []
        for chart in self._charts:
            if filter_value == "Subscribed" and not chart.subscribed:
                continue
            if filter_value == "Unsubscribed" and chart.subscribed:
                continue
            if self._active_search not in chart.name.casefold():
                continue
            visible_charts.append(chart)

        # Replace the visible rows and result summary
        self._chart_list.show_charts(visible_charts)
        self._status.setText(
            f"{len(visible_charts)} of {len(self._charts)} charts"
        )

    # Reports

    def _show_sync_report(self, report: schema.SyncReport) -> None:
        message = self._format_sync_report(report)
        if report.failed:
            QMessageBox.warning(self, "Sync completed with errors", message)
        else:
            QMessageBox.information(self, "Sync completed", message)

    @staticmethod
    def _format_sync_report(report: schema.SyncReport) -> str:
        lines = [
            f"Subscribed charts: {report.subscribed}",
            f"Updated: {report.updated}",
            f"Up to date: {report.up_to_date}",
            f"Missing from remote: {report.missing}",
            f"Failed: {report.failed}",
        ]
        if report.failures:
            lines.extend(("", "Failures:", *report.failures))
        return "\n".join(lines)
