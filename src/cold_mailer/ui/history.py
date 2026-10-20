"""Paged, read-only ledger of actual transport attempts."""

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as daytime
from pathlib import Path
from sqlite3 import Error as DatabaseError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PySide6.QtCore import QDate, QTimer, Slot
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from cold_mailer.domain.models import ValidationError
from cold_mailer.infrastructure.history import export_history
from cold_mailer.infrastructure.storage import Store
from cold_mailer.ui.callbacks import weak_callback
from cold_mailer.ui.components import field
from cold_mailer.ui.workers import Operation


@dataclass(frozen=True)
class HistoryQuery:
    query: str
    outcome: str
    offset: int
    timezone: str
    since: float | None
    until: float | None


@dataclass(frozen=True)
class HistoryExported:
    count: int


class HistoryPage(QWidget):
    def __init__(self, store: Store, start: Callable[[Operation], None] | None = None) -> None:
        super().__init__()
        self.store = store
        self.offset = 0
        self.rows: list[dict[str, object]] = []
        self.start = weak_callback(start) if start else None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="history-reader")
        self.future: Future[list[dict[str, object]]] | None = None
        self.active: tuple[int, HistoryQuery] | None = None
        self.pending: tuple[int, HistoryQuery] | None = None
        self.token = 0
        self.saved_timezone = store.preference("history.timezone", "UTC")
        self.display_timezone = ZoneInfo("UTC")
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.poll)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Provider acceptance is separate from delivery. Display times use your chosen timezone; CSV timestamps remain UTC."
            )
        )
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search sender, recipient, subject, or body")
        self.outcome = QComboBox()
        self.outcome.addItems(
            ["All outcomes", "accepted", "failed", "retryable", "uncertain", "sending"]
        )
        bar.addWidget(self.search, 1)
        bar.addWidget(self.outcome)
        for text, callback in (
            ("Search / refresh", self.refresh),
            ("Export matching CSV", self.export),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            bar.addWidget(button)
        self.search.returnPressed.connect(self.refresh)
        layout.addLayout(bar)
        dates = QHBoxLayout()
        self.use_dates = QCheckBox("Filter dates")
        self.from_date, self.to_date = (
            QDateEdit(QDate.currentDate()),
            QDateEdit(QDate.currentDate()),
        )
        for control in (self.from_date, self.to_date):
            control.setCalendarPopup(True)
            control.setDisplayFormat("yyyy-MM-dd")
            control.setMinimumWidth(180)
        self.timezone = QLineEdit(self.saved_timezone)
        self.timezone.setPlaceholderText("IANA timezone, e.g. Asia/Karachi")
        dates.addWidget(self.use_dates)
        dates.addWidget(field("From (inclusive)", self.from_date))
        dates.addWidget(field("Through (inclusive)", self.to_date))
        dates.addWidget(field("Display / date-filter timezone", self.timezone), 1)
        layout.addLayout(dates)
        self.table = QTableView()
        self.model = QStandardItemModel(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.table.selectionModel().currentRowChanged.connect(self.select)
        layout.addWidget(self.table, 2)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview, 1)
        paging = QHBoxLayout()
        for text, callback in (("Previous page", self.previous), ("Next page", self.next)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            paging.addWidget(button)
        self.count = QLabel()
        paging.addWidget(self.count)
        layout.addLayout(paging)

    @Slot()
    def refresh(self) -> None:
        self.offset = 0
        self.load()

    def query(self) -> HistoryQuery:
        name = self.timezone.text().strip()
        try:
            zone = ZoneInfo(name)
        except ZoneInfoNotFoundError, ValueError:
            raise ValidationError("Choose a valid IANA display timezone.") from None
        since, until = None, None
        if self.use_dates.isChecked():
            lower, upper = self.from_date.date().toPython(), self.to_date.date().toPython()
            if not isinstance(lower, date) or not isinstance(upper, date):
                raise ValidationError("Choose valid start and end dates.")
            if lower > upper:
                raise ValidationError("The final date must not precede the first date.")
            since = datetime.combine(lower, daytime.min, zone).timestamp()
            until = datetime.combine(upper + timedelta(days=1), daytime.min, zone).timestamp()
        return HistoryQuery(
            self.search.text(),
            "" if self.outcome.currentIndex() == 0 else self.outcome.currentText(),
            self.offset,
            name,
            since,
            until,
        )

    @Slot()
    def load(self) -> None:
        self.token += 1
        try:
            query = self.query()
            if query.timezone != self.saved_timezone:
                self.store.save_preference("history.timezone", query.timezone)
                self.saved_timezone = query.timezone
        except (ValidationError, OSError, DatabaseError) as exc:
            self.pending = None
            self.count.setText(str(exc))
            return
        self.pending = (self.token, query)
        self.count.setText("Searching history…")
        self.table.setEnabled(False)
        if self.future is None:
            self.submit()

    def submit(self) -> None:
        if self.pending is None:
            return
        self.active, self.pending = self.pending, None
        query = self.active[1]
        self.future = self.executor.submit(
            self.store.history,
            query.query,
            query.outcome,
            offset=query.offset,
            since=query.since,
            until=query.until,
        )
        self.timer.start()

    @Slot()
    def poll(self) -> None:
        future = self.future
        if future is None or not future.done():
            return
        self.future = None
        try:
            rows = future.result()
            if self.active and self.active[0] == self.token:
                self.display_timezone = ZoneInfo(self.active[1].timezone)
                self.rows = rows
                self.render_rows()
        except Exception:
            if self.active and self.active[0] == self.token:
                self.count.setText(
                    "Search could not finish. Narrow the date range or search and retry; stored mail is unchanged."
                )
        if self.pending:
            self.submit()
        else:
            self.table.setEnabled(True)
            self.timer.stop()

    def display_time(self, value: object) -> str:
        return (
            datetime.fromtimestamp(float(str(value)), UTC)
            .astimezone(self.display_timezone)
            .isoformat()
            if value is not None
            else "Unknown"
        )

    def render_rows(self) -> None:
        self.model.clear()
        self.model.setHorizontalHeaderLabels(
            [f"Started ({self.display_timezone.key})", "Outcome", "Sender", "Recipient", "Subject"]
        )
        for row in self.rows:
            self.model.appendRow(
                [
                    QStandardItem(value)
                    for value in (
                        self.display_time(row["started"]),
                        str(row["outcome"]),
                        str(row["sender_email"] or "Unknown (legacy)"),
                        str(row["recipient"] or "Unknown (legacy)"),
                        str(row["subject"] or ""),
                    )
                ]
            )
        self.table.resizeColumnsToContents()
        self.preview.clear()
        self.count.setText(f"Page {self.offset // 100 + 1} · {len(self.rows)} attempts")

    @Slot()
    def select(self) -> None:
        index = self.table.currentIndex().row()
        if 0 <= index < len(self.rows):
            row = self.rows[index]
            self.preview.setPlainText(
                f"Campaign: {row['campaign']}\nFinished ({self.display_timezone.key}): {self.display_time(row['finished'])}\nOutcome: {row['outcome']} / {row['code']}\nSubject: {row['subject'] or 'Unknown (legacy)'}\n\n{row['body'] or 'No historical content snapshot available.'}"
            )

    @Slot()
    def previous(self) -> None:
        if self.future is not None:
            return
        self.offset = max(0, self.offset - 100)
        self.load()

    @Slot()
    def next(self) -> None:
        if self.future is not None:
            return
        if len(self.rows) == 100:
            self.offset += 100
            self.load()

    @Slot()
    def export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export private history to a NEW file", "", "CSV (*.csv)"
        )
        if path:
            try:
                query = self.query()

                def operation(stop, emit):
                    return HistoryExported(
                        export_history(
                            self.store,
                            Path(path),
                            query.query,
                            query.outcome,
                            since=query.since,
                            until=query.until,
                            cancelled=stop.is_set,
                        )
                    )

                if self.start:
                    self.start(operation)
                else:
                    count = export_history(
                        self.store,
                        Path(path),
                        query.query,
                        query.outcome,
                        since=query.since,
                        until=query.until,
                    )
                    self.count.setText(f"Exported {count} attempts. Treat this file as private.")
            except OSError, ValidationError:
                self.count.setText("Export failed. Choose a new file and check permissions.")

    def shutdown(self) -> None:
        self.pending = None
        self.timer.stop()
        if self.future:
            self.future.cancel()
        self.executor.shutdown(wait=False, cancel_futures=True)
