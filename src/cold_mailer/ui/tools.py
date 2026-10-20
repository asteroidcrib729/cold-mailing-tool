"""Local campaign controls, provenance review and recovery, separate from the main window."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from PySide6.QtCore import QTime, QTimer, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from cold_mailer.domain.models import Message, ValidationError
from cold_mailer.domain.scheduling import SendWindow
from cold_mailer.infrastructure.backup import restore_encrypted
from cold_mailer.infrastructure.feedback import PreparedFeedback, read_feedback, record_feedback
from cold_mailer.infrastructure.organization import GenerationBudget, Organization
from cold_mailer.infrastructure.storage import Store
from cold_mailer.infrastructure.workspaces import launch_workspace
from cold_mailer.ui.callbacks import weak_callback
from cold_mailer.ui.components import Card, field, label, scroll_content
from cold_mailer.ui.workers import Operation


class CampaignTools(QWidget):
    def __init__(
        self,
        store: Store,
        current_campaign: Callable[[], str],
        current_message: Callable[[], Message | None],
        start: Callable[[Operation], None],
        refresh: Callable[[], None],
        can_modify: Callable[[], bool],
    ) -> None:
        super().__init__()
        self.store, self.organization = store, Organization(store)
        self.current_campaign, self.current_message, self.start, self.refresh = (
            weak_callback(current_campaign),
            weak_callback(current_message),
            weak_callback(start),
            weak_callback(refresh),
        )
        self.can_modify = weak_callback(can_modify)
        self.workspace_processes = []
        self.workspace_timer = QTimer(self)
        self.workspace_timer.setInterval(1000)
        self.workspace_timer.timeout.connect(self.reap_workspaces)
        layout = QVBoxLayout(self)
        scroll, _, content = scroll_content()
        layout.addWidget(scroll)
        self.status = label("Local controls · provider calls and sending remain explicit.")
        content.addWidget(self.status)
        try:
            window = SendWindow.load(store.preference("sending.window", "{}"))
        except ValidationError:
            window = SendWindow()
            self.status.setText(
                "Stored sending controls are invalid. Review and save them below; existing records are preserved until then."
            )
        try:
            budget = GenerationBudget.load(store)
        except ValidationError:
            budget = GenerationBudget()
            self.status.setText(
                self.status.text() + " Generation budget is invalid; review and save it to repair."
            )
        schedule = Card(
            "Sending windows",
            "This is an admission safeguard, not an automatic-send schedule. Blocked messages stay approved for a later explicit run.",
        )
        self.window_enabled = QCheckBox("Use allowed local-time sending windows")
        self.window_enabled.setChecked(window.enabled)
        self.contact_zone = QCheckBox(
            "Use each contact's timezone field; hold missing or invalid timezones"
        )
        self.contact_zone.setChecked(window.use_contact_timezone)
        self.timezone = QLineEdit(window.timezone)
        self.start_time = QTimeEdit(QTime(window.start_minute // 60, window.start_minute % 60))
        self.end_time = QTimeEdit(QTime(window.end_minute // 60, window.end_minute % 60))
        self.start_time.setDisplayFormat("HH:mm")
        self.end_time.setDisplayFormat("HH:mm")
        self.days = []
        days = QHBoxLayout()
        for index, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            check = QCheckBox(name)
            check.setChecked(index in window.days)
            days.addWidget(check)
            self.days.append(check)
        schedule.content.addWidget(self.window_enabled)
        schedule.content.addWidget(
            field(
                "Default IANA timezone",
                self.timezone,
                "For example: Asia/Karachi, Europe/London, America/New_York. No timezone is guessed from an address.",
            )
        )
        times = QHBoxLayout()
        times.addWidget(field("Start (inclusive)", self.start_time))
        times.addWidget(field("End (exclusive)", self.end_time))
        schedule.content.addLayout(times)
        schedule.content.addLayout(days)
        schedule.content.addWidget(self.contact_zone)
        self.add_button(schedule, "Save sending window", self.save_window)
        self.add_button(
            schedule, "Preview selected recipient's next allowed time", self.preview_window
        )
        content.addWidget(schedule)
        generation = Card(
            "Generation request budget",
            "Requests, including failed or interrupted admissions, count conservatively. Costs below use only your optional planning value; they are not provider bills.",
        )
        self.per_run, self.per_day = QSpinBox(), QSpinBox()
        for control, value in ((self.per_run, budget.per_run), (self.per_day, budget.per_day)):
            control.setRange(1, 10_000)
            control.setValue(value)
        self.price = QDoubleSpinBox()
        self.price.setDecimals(6)
        self.price.setRange(0, 1000)
        self.price.setValue(budget.price_per_request)
        generation.content.addWidget(field("Maximum requests per operation", self.per_run))
        generation.content.addWidget(field("Maximum requests per rolling 24 hours", self.per_day))
        generation.content.addWidget(
            field("Optional planning units per request (0 = unknown)", self.price)
        )
        self.add_button(generation, "Save generation budget", self.save_budget)
        self.add_button(generation, "Preview current request allowance", self.preview_budget)
        content.addWidget(generation)
        review = Card(
            "Evidence and recovery",
            "Feedback files are unverified local evidence. Reply and opt-out linking checks the original Message-ID and recipient; nothing contacts an inbox.",
        )
        for text, callback in (
            ("Review selected recipient's source records", self.show_sources),
            ("Compare or restore a saved revision", self.restore_revision),
            ("Review a local reply file (.eml)", self.import_feedback),
            ("Show campaign outcome report", self.show_report),
            ("Restore a backup into a NEW workspace", self.restore_backup),
        ):
            self.add_button(review, text, callback)
        content.addWidget(review)
        workspaces = Card(
            "Separate workspaces",
            "Open an empty folder or an existing workspace in another window. Credentials and campaign state remain separate; provider limits still apply across applications.",
        )
        self.add_button(workspaces, "Open another workspace", self.open_workspace)
        content.addWidget(workspaces)
        content.addStretch()

    def add_button(self, card: Card, text: str, callback: Callable[[], None]) -> None:
        button = QPushButton(text)
        button.setMinimumHeight(40)
        button.clicked.connect(callback)
        card.content.addWidget(button)

    def guard(self, action: Callable[[], None]) -> None:
        try:
            action()
        except ValidationError as exc:
            self.status.setText(str(exc))
        except Exception:
            self.status.setText(
                "The local operation failed. Current data was preserved; check storage and input before retrying."
            )

    def window_policy(self) -> SendWindow:
        start, end = self.start_time.time(), self.end_time.time()
        value = SendWindow(
            self.window_enabled.isChecked(),
            self.timezone.text().strip(),
            start.hour() * 60 + start.minute(),
            end.hour() * 60 + end.minute(),
            tuple(index for index, check in enumerate(self.days) if check.isChecked()),
            self.contact_zone.isChecked(),
        )
        value.validate()
        return value

    @Slot()
    def save_window(self) -> None:
        def save() -> None:
            self.store.save_preference("sending.window", json.dumps(asdict(self.window_policy())))
            self.status.setText(
                "Sending window saved. Account pacing, approvals and suppression still apply."
            )

        self.guard(save)

    @Slot()
    def preview_window(self) -> None:
        def preview() -> None:
            message = self.current_message()
            value = self.window_policy()
            when = value.next_time(message.contact if message else {}, time.time())
            self.status.setText(
                "Next allowed instant (UTC): " + when.isoformat()
                if when
                else "Held: select a recipient with a valid explicit timezone. No time was inferred."
            )

        self.guard(preview)

    @Slot()
    def save_budget(self) -> None:
        def save() -> None:
            value = GenerationBudget(self.per_run.value(), self.per_day.value(), self.price.value())
            self.store.save_preference("generation.budget", json.dumps(asdict(value)))
            self.status.setText(
                "Generation request limits saved. Already reserved requests remain counted."
            )

        self.guard(save)

    @Slot()
    def preview_budget(self) -> None:
        def preview() -> None:
            available = self.organization.available_requests()
            policy = GenerationBudget.load(self.store)
            price = (
                f"{available * policy.price_per_request:.6f} user-defined planning units"
                if policy.price_per_request
                else "cost unknown (no planning value configured)"
            )
            self.status.setText(
                f"At most {available} requests available for the next operation; {price}. Output tokens and actual billing may differ."
            )

        self.guard(preview)

    def text_dialog(self, title: str, text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(760, 520)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit(text)
        view.setReadOnly(True)
        layout.addWidget(view)
        dialog.exec()

    def selected(self) -> Message:
        message = self.current_message()
        if message is None:
            raise ValidationError("Select a recipient in Campaigns first.")
        return self.store.message(message.id)

    @Slot()
    def show_sources(self) -> None:
        def show() -> None:
            rows = self.organization.sources(self.selected().id)
            self.text_dialog(
                "Source / permission records · operator statements",
                "\n\n".join(
                    f"Source: {row['source_label']}\nRecorded (UTC): {datetime.fromtimestamp(int(str(row['created_us'])) / 1e6, UTC).isoformat()}\nReviewed: {'Yes' if row['reviewed'] else 'Not recorded'}\nNotes: {row['permission_note'] or 'Not recorded'}\nFile SHA-256: {row['source_sha256']}"
                    for row in rows
                )
                if rows
                else "No source record is available for this older or manually created contact. Absence does not establish permission.",
            )

        self.guard(show)

    @Slot()
    def show_report(self) -> None:
        def show() -> None:
            report = self.organization.report(self.current_campaign())
            attempts = cast(dict[str, int], report["transport_attempts"])
            feedback = cast(dict[str, int], report["operator_reviewed_feedback"])
            runs = cast(list[object], report["frozen_runs"])
            lines = [
                "TRANSPORT ATTEMPTS (not unique recipients)",
                *[f"{kind.title()}: {count}" for kind, count in attempts.items()],
                "",
                "OPERATOR-REVIEWED FEEDBACK",
                *[f"{kind.title()}: {count}" for kind, count in feedback.items()],
                "",
                f"Generation requests reserved: {report['generation_requests']}",
                "",
                str(report["delivery_status"]),
                "",
                f"Recorded frozen runs: {len(runs)} (up to the latest 100)",
            ]
            self.text_dialog(
                "Campaign outcomes · acceptance is separate from delivery", "\n".join(lines)
            )

        self.guard(show)

    @Slot()
    def restore_revision(self) -> None:
        def restore() -> None:
            if not self.can_modify():
                raise ValidationError(
                    "Save or discard pending editor changes before restoring a revision."
                )
            message = self.selected()
            rows = self.store.revisions(message.id)
            if not rows:
                raise ValidationError("No saved revisions are available.")
            names = [
                f"Revision {row['revision']} · {row['origin']} · {datetime.fromtimestamp(int(str(row['saved_us'])) / 1e6, UTC).isoformat()}"
                for row in rows
            ]
            chosen, ok = QInputDialog.getItem(
                self,
                "Choose a saved revision",
                "Current content is preserved until you confirm the comparison",
                names,
                0,
                False,
            )
            if not ok or chosen not in names:
                return
            saved = rows[names.index(chosen)]
            dialog = QDialog(self)
            dialog.setWindowTitle("Compare saved and current draft")
            dialog.resize(900, 580)
            layout = QVBoxLayout(dialog)
            columns = QHBoxLayout()
            for title, subject, body in (
                ("Current", message.subject, message.body),
                ("Saved revision", str(saved["subject"]), str(saved["body"])),
            ):
                view = QPlainTextEdit(title + "\n" + subject + "\n\n" + body)
                view.setReadOnly(True)
                columns.addWidget(view)
            layout.addLayout(columns)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.button(QDialogButtonBox.StandardButton.Save).setText(
                "Restore as a new unapproved draft"
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.organization.restore_revision(message.id, str(saved["id"]), message.revision)
                self.refresh()
                self.status.setText(
                    "Revision restored as a new draft; review and approve it again."
                )

        self.guard(restore)

    @Slot()
    def import_feedback(self) -> None:
        def prepare() -> None:
            message = self.selected()
            path, _ = QFileDialog.getOpenFileName(
                self, "Review a local reply file", "", "Email (*.eml)"
            )
            if path:
                self.start(
                    lambda stop, emit: PreparedFeedback(message.id, read_feedback(Path(path)))
                )

        self.guard(prepare)

    def receive(self, value: object) -> bool:
        if not isinstance(value, PreparedFeedback):
            return False
        dialog = QDialog(self)
        dialog.setWindowTitle("Review unverified local feedback")
        dialog.resize(760, 550)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            label(
                "This file does not authenticate authorship. Opt-out classification adds the address to suppression after your confirmation. HTML, attachments and remote images are not rendered."
            )
        )
        view = QPlainTextEdit(
            f"From: {value.document.sender}\nSubject: {value.document.subject}\n\n{value.document.body}"
        )
        view.setReadOnly(True)
        layout.addWidget(view, 1)
        kind = QComboBox()
        kind.addItems(["reply", "optout", "note"])
        layout.addWidget(field("Operator classification", kind))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:

            def record() -> None:
                added = record_feedback(
                    self.store, value.message_id, value.document, kind.currentText()
                )
                self.status.setText(
                    "Reviewed feedback recorded."
                    if added
                    else "This file was already recorded; no duplicate was added."
                )
                self.refresh()

            self.guard(record)
        return True

    @Slot()
    def restore_backup(self) -> None:
        def prepare() -> None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose backup to restore", "", "Backup (*.cmbak *.sqlite3)"
            )
            if not path:
                return
            destination, _ = QFileDialog.getSaveFileName(
                self,
                "NEW empty workspace folder / campaigns.sqlite3",
                "campaigns.sqlite3",
                "SQLite (*.sqlite3)",
            )
            if not destination:
                return
            target = Path(destination).resolve()
            if (
                target.name != "campaigns.sqlite3"
                or target.parent == self.store.path.parent
                or (target.parent.exists() and any(target.parent.iterdir()))
            ):
                raise ValidationError(
                    "Choose campaigns.sqlite3 inside a NEW empty workspace folder."
                )
            if Path(path).suffix.lower() == ".cmbak":
                password, ok = QInputDialog.getText(
                    self, "Decrypt backup", "Backup passphrase", QLineEdit.EchoMode.Password
                )
                if not ok:
                    return
                self.start(lambda stop, emit: restore_encrypted(Path(path), target, password))
            else:
                self.start(lambda stop, emit: Store.restore(Path(path), target))
            self.status.setText(
                "Restoring into the new workspace. Pending messages are held uncertain; passwords must be re-entered."
            )

        self.guard(prepare)

    @Slot()
    def open_workspace(self) -> None:
        def open_selected() -> None:
            self.reap_workspaces()
            if len(self.workspace_processes) >= 8:
                raise ValidationError("Close an extra workspace window before opening another.")
            directory = QFileDialog.getExistingDirectory(
                self, "Choose an empty or existing Cold Mailer workspace"
            )
            if directory:
                self.workspace_processes.append(launch_workspace(Path(directory)))
                self.workspace_timer.start()
                self.status.setText(
                    "Opened a separate workspace with live access off and no copied API credentials."
                )

        self.guard(open_selected)

    @Slot()
    def reap_workspaces(self) -> None:
        self.workspace_processes = [
            process for process in self.workspace_processes if process.poll() is None
        ]
        if not self.workspace_processes:
            self.workspace_timer.stop()
