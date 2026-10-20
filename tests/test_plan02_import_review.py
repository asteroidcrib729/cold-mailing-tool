import hashlib
import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from cold_mailer.domain.models import ImportSource, ValidationError
from cold_mailer.infrastructure.contacts import mapped_columns, read_document
from cold_mailer.infrastructure.organization import Organization
from cold_mailer.ui.imports import ContactImportDialog, PreparedImport
from tests.conftest import Rig

pytestmark = pytest.mark.integration


def test_mapping_preview_diagnostics_and_atomic_source_records(rig: Rig, tmp_path: Path) -> None:
    path = tmp_path / "export.csv"
    path.write_text(
        "Email Address,Given Name,Code,Unused\nalex@example.com,Alex,00123,private\ninvalid,Bad,2,x\nalex@example.com,Duplicate,3,x\nwrong,row\n",
        encoding="utf-8-sig",
    )
    before = path.read_bytes()
    document = read_document(path)
    mapping = {"Email Address": "email", "Given Name": "first_name", "Code": "code", "Unused": ""}
    report = document.parse(mapping)
    assert report.contacts == [{"email": "alex@example.com", "first_name": "Alex", "code": "00123"}]
    assert len(report.issues) == 2 and report.duplicates == 1
    source = ImportSource(
        "Reviewed export", document.sha256, "Imported from our recorded source", True
    )
    assert rig.store.add_contacts(rig.campaign, rig.sender.id, report.contacts, source=source) == 1
    message = rig.store.messages(rig.campaign)[0]
    rows = Organization(rig.store).sources(message.id)
    assert rows[0]["permission_note"] == source.permission_note and rows[0]["reviewed"] == 1
    changed = [{"email": message.recipient, "first_name": "Must not silently merge"}]
    assert rig.store.add_contacts(rig.campaign, rig.sender.id, changed, source=source) == 0
    assert rig.store.message(message.id).contact["first_name"] == "Alex"
    assert len(Organization(rig.store).sources(message.id)) == 2
    assert path.read_bytes() == before
    path.write_text("Email Address\nchanged@example.com\n")
    with pytest.raises(ValidationError, match="changed"):
        read_document(path, expected_sha256=document.sha256)


@pytest.mark.parametrize(
    "mapping",
    [
        {"Source": "first_name"},
        {"Source": "email", "Other": "email"},
        {"Source": "email", "Other": "bad-field"},
        {"Source": "email", "Unknown": "other"},
    ],
)
def test_invalid_or_ambiguous_destination_mapping_is_rejected(mapping: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        mapped_columns(("Source", "Other"), mapping)


def test_bounded_workbook_and_csv_validation(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "mapped.xlsx"
    book = Workbook()
    assert book.active is not None
    book.active.append(["Email Address", "Given Name"])
    book.active.append(["a@example.com", "=1+1"])
    book.save(path)
    document = read_document(path)
    assert (
        document.parse({"Email Address": "email", "Given Name": "first_name"}).contacts[0][
            "first_name"
        ]
        == "=1+1"
    )
    for index, raw in enumerate((b"Email,email\na,b\n", b"\xff", b"", b",Name\na,b\n")):
        invalid = tmp_path / f"invalid{index}.csv"
        invalid.write_bytes(raw)
        with pytest.raises(ValidationError):
            read_document(invalid)
    unsupported = tmp_path / "file.xls"
    unsupported.write_bytes(b"synthetic")
    with pytest.raises(ValidationError):
        read_document(unsupported)
    import cold_mailer.infrastructure.contacts as contacts

    monkeypatch.setattr(contacts, "MAX_ROWS", 1)
    many = tmp_path / "many.csv"
    many.write_text("email\na@example.com\nb@example.com\n")
    with pytest.raises(ValidationError):
        read_document(many)


@pytest.mark.ui
def test_mapping_dialog_saved_profiles_and_validation(qtbot, rig: Rig, tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    path.write_text("Email Address,Given Name\na@example.com,Alex\n")
    prepared = PreparedImport(path, read_document(path), rig.campaign, rig.sender.id, None)
    dialog = ContactImportDialog(prepared, rig.store)
    qtbot.addWidget(dialog)
    assert dialog.mapping() == {"Email Address": "email", "Given Name": "first_name"}
    dialog.controls["Email Address"].setCurrentText("first_name")
    dialog.accept()
    assert "exactly one" in dialog.error.text()
    dialog.controls["Email Address"].setCurrentText("email")
    dialog.profile_name.setText("Supplier A")
    dialog.reviewed.setChecked(True)
    dialog.permission_note.setText("Operator reviewed the source")
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted
    profiles = json.loads(rig.store.preference("import.mappings"))
    assert profiles["Supplier A"]["Email Address"] == "email"
    reopened = ContactImportDialog(prepared, rig.store)
    qtbot.addWidget(reopened)
    reopened.controls["Email Address"].setCurrentText("")
    reopened.profiles.setCurrentIndex(1)
    assert reopened.mapping()["Email Address"] == "email"
    assert not rig.store.messages(rig.campaign)


def test_import_source_validation_and_transaction_rollback(rig: Rig) -> None:
    source = ImportSource("source", hashlib.sha256(b"synthetic").hexdigest())
    with pytest.raises(ValidationError):
        ImportSource("", "bad").validate()
    with pytest.raises(ValidationError):
        rig.store.add_contacts(
            rig.campaign,
            rig.sender.id,
            [{"email": "valid@example.com"}, {"email": "invalid"}],
            source=source,
        )
    assert not rig.store.messages(rig.campaign)
    with rig.store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0] == 0
