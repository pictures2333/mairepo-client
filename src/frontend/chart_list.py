from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src import schema


class ClickableLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ChartRow(QFrame):
    subscription_changed = Signal(int, bool)
    expansion_changed = Signal(int, bool)

    def __init__(
        self,
        chart: schema.Chart,
        subscribed: bool,
        expanded: bool,
    ) -> None:
        super().__init__()
        self._chart_id = chart.id
        self._expanded = expanded
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        text = QVBoxLayout()

        name = ClickableLabel(chart.name)
        name_font = name.font()
        name_font.setBold(True)
        name.setFont(name_font)
        name.setCursor(Qt.CursorShape.PointingHandCursor)
        name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        name.clicked.connect(self._toggle_details)
        text.addWidget(name)

        subscription = "Subscribed" if subscribed else "Not subscribed"
        summary = ClickableLabel(
            f"ID {chart.id} | {len(chart.files)} files | {subscription}"
        )
        summary.setCursor(Qt.CursorShape.PointingHandCursor)
        summary.clicked.connect(self._toggle_details)
        text.addWidget(summary)

        button = QPushButton("Unsubscribe" if subscribed else "Subscribe")
        button.clicked.connect(
            lambda: self.subscription_changed.emit(chart.id, not subscribed)
        )

        header.addLayout(text, 1)
        header.addWidget(button)
        layout.addLayout(header)

        self._details = QWidget()
        details_layout = QVBoxLayout(self._details)
        details_layout.setContentsMargins(12, 4, 0, 0)
        if chart.files:
            for chart_file in chart.files:
                details_layout.addWidget(
                    QLabel(
                        f"{chart_file.filename} "
                        f"({len(chart_file.blobs)} versions)"
                    )
                )
        else:
            details_layout.addWidget(QLabel("No files."))
        self._details.setVisible(expanded)
        layout.addWidget(self._details)

    def _toggle_details(self) -> None:
        self._expanded = not self._expanded
        self._details.setVisible(self._expanded)
        self.expansion_changed.emit(self._chart_id, self._expanded)


class ChartList(QScrollArea):
    subscription_changed = Signal(int, bool)

    def __init__(self) -> None:
        super().__init__()
        self._expanded_chart_ids: set[int] = set()

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self.setWidget(self._content)

    def show_charts(
        self,
        charts: list[schema.Chart],
        subscribed_chart_ids: set[int],
    ) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not charts:
            self._layout.addWidget(QLabel("No charts match the current filter."))
            self._layout.addStretch()
            return

        for chart in charts:
            row = ChartRow(
                chart,
                subscribed=chart.id in subscribed_chart_ids,
                expanded=chart.id in self._expanded_chart_ids,
            )
            row.subscription_changed.connect(self.subscription_changed)
            row.expansion_changed.connect(self._set_expanded)
            self._layout.addWidget(row)
        self._layout.addStretch()

        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.minimum())

    def _set_expanded(self, chart_id: int, expanded: bool) -> None:
        if expanded:
            self._expanded_chart_ids.add(chart_id)
        else:
            self._expanded_chart_ids.discard(chart_id)
