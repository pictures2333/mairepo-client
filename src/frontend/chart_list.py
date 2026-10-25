from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src import schema

# Chart widgets


class ChartRow(QFrame):
    subscription_requested = Signal(int, bool)

    def __init__(
        self,
        chart: schema.ChartState,
    ) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)

        # Chart summary
        layout = QHBoxLayout(self)
        text = QVBoxLayout()

        name = QLabel(chart.name)
        name_font = name.font()
        name_font.setBold(True)
        name.setFont(name_font)
        text.addWidget(name)

        if chart.missing:
            status = "Missing from remote"
        elif not chart.subscribed:
            status = "Not subscribed"
        elif chart.outdated:
            status = "Outdated"
        else:
            status = "Up to date"
        summary = QLabel(f"ID {chart.id} | {status}")
        text.addWidget(summary)

        # Subscription action
        button = QPushButton("Unsubscribe" if chart.subscribed else "Subscribe")
        button.clicked.connect(
            lambda: self.subscription_requested.emit(
                chart.id,
                not chart.subscribed,
            )
        )

        layout.addLayout(text, 1)
        layout.addWidget(button)


# Scrollable chart list


class ChartList(QScrollArea):
    subscription_requested = Signal(int, bool)

    def __init__(self) -> None:
        super().__init__()

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self.setWidget(self._content)

    def show_charts(
        self,
        charts: list[schema.ChartState],
    ) -> None:
        # Clear current rows
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Empty state
        if not charts:
            self._layout.addWidget(QLabel("No charts match the current filter."))
            self._layout.addStretch()
            return

        # Chart rows
        for chart in charts:
            row = ChartRow(chart)
            row.subscription_requested.connect(self.subscription_requested)
            self._layout.addWidget(row)
        self._layout.addStretch()

        # Reset scroll after replacing results
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.minimum())
