"""Review column mapping and source notes before writing any contacts."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cold_mailer.domain.models import ImportSource, ValidationError
from cold_mailer.infrastructure.contacts import ContactDocument, mapped_columns
from cold_mailer.infrastructure.storage import Store
from cold_mailer.ui.components import field, label

FIELDS = (
    "email",
    "first_name",
    "last_name",
    "company_name",
    "job_title",
    "industry",
    "timezone",
    "tags",
)
ALIASES = {
    "email_address": "email",
    "e_mail": "email",
    "given_name": "first_name",
    "surname": "last_name",
    "company": "company_name",
}


@dataclass(frozen=True)
class PreparedImport:
    path: Path
    document: ContactDocument
    campaign_id: str
    sender_id: str
    rotation: list[str] | None


class ContactImportDialog(QDialog):
    def __init__(
        self, prepared: PreparedImport, store: Store, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.prepared, self.store = prepared, store
        self.setWindowTitle("Review contact import")
        self.resize(820, 650)
        layout = QVBoxLayout(self)
        layout.addWidget(
            label(
                f"{len(prepared.document.rows)} source rows. Preview examples below, map one email column, then import. The source file is never modified."
            )
        )
        mapping_bar = QHBoxLayout()
        self.profiles = QComboBox()
        self.profiles.addItem("Choose a saved mapping", None)
        profiles = json.loads(store.preference("import.mappings", "{}"))
        if not isinstance(profiles, dict):
            profiles = {}
        self.saved_profiles = profiles
        for name in sorted(profiles):
            self.profiles.addItem(name, name)
        self.profiles.currentIndexChanged.connect(self.load_profile)
        mapping_bar.addWidget(self.profiles)
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("Optional mapping name to save")
        mapping_bar.addWidget(self.profile_name)
        layout.addLayout(mapping_bar)
        self.table = QTableWidget(len(prepared.document.headers), 3)
        self.table.setHorizontalHeaderLabels(
            ["Source column", "First nonempty example", "Import as (blank to ignore)"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.controls: dict[str, QComboBox] = {}
        for index, header in enumerate(prepared.document.headers):
            self.table.setItem(index, 0, QTableWidgetItem(header))
            example = next(
                (
                    str(row[index])
                    for row in prepared.document.rows[:20]
                    if index < len(row) and row[index] is not None and str(row[index]).strip()
                ),
                "",
            )
            self.table.setItem(index, 1, QTableWidgetItem(example[:200]))
            control = QComboBox()
            control.setEditable(True)
            control.addItems(["", *FIELDS])
            normalized = re.sub(r"[^a-z0-9_]+", "_", header.lower()).strip("_")
            control.setCurrentText(ALIASES.get(normalized, normalized))
            self.table.setCellWidget(index, 2, control)
            self.controls[header] = control
        layout.addWidget(self.table, 1)
        self.source_label = QLineEdit(prepared.path.name)
        self.source_label.setMaxLength(200)
        self.permission_note = QLineEdit()
        self.permission_note.setMaxLength(2000)
        self.reviewed = QCheckBox(
            "I reviewed the source and recorded the contact-permission context"
        )
        layout.addWidget(field("Source label", self.source_label))
        layout.addWidget(field("Source / permission notes (optional)", self.permission_note))
        layout.addWidget(self.reviewed)
        layout.addWidget(
            label(
                "These are your records, not a legal or delivery certification. Missing notes remain marked unreviewed.",
                "hint",
            )
        )
        self.error = label("", "hint")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import reviewed mapping")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def mapping(self) -> dict[str, str]:
        return {
            header: control.currentText().strip().lower()
            for header, control in self.controls.items()
        }

    def source(self) -> ImportSource:
        return ImportSource(
            self.source_label.text(),
            self.prepared.document.sha256,
            self.permission_note.text(),
            self.reviewed.isChecked(),
        )

    @Slot()
    def load_profile(self) -> None:
        profile = self.saved_profiles.get(self.profiles.currentData())
        if not isinstance(profile, dict) or set(profile) != set(self.controls):
            if self.profiles.currentIndex() > 0:
                self.error.setText(
                    "This mapping uses different headers. Current choices were preserved."
                )
            return
        for header, control in self.controls.items():
            control.setCurrentText(str(profile[header]))
        self.error.clear()

    @Slot()
    def accept(self) -> None:
        try:
            mapped_columns(self.prepared.document.headers, self.mapping())
            self.source().validate()
            name = self.profile_name.text().strip()
            if len(name) > 80:
                raise ValidationError("Mapping names must be at most 80 characters.")
            if name:
                self.saved_profiles[name] = self.mapping()
                self.store.save_preference("import.mappings", json.dumps(self.saved_profiles))
        except ValidationError as exc:
            self.error.setText(str(exc))
            return
        except Exception:
            self.error.setText(
                "Mapping could not be saved. Check profile storage; no contacts were imported."
            )
            return
        super().accept()
