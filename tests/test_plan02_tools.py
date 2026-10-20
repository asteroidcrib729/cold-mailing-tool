import json
import sqlite3
import zipfile
from pathlib import Path
from threading import Event

import pytest

from cold_mailer.application.review import quality_hints, reading_preview
from cold_mailer.bootstrap import Application
from cold_mailer.domain.models import Status, ValidationError
from cold_mailer.infrastructure.backup import MAGIC, encrypted_backup, restore_encrypted
from cold_mailer.infrastructure.demo import DemoGenerator
from cold_mailer.infrastructure.doctor import diagnostics
from cold_mailer.infrastructure.storage import Store
from cold_mailer.infrastructure.support import support_preview, write_support_bundle
from cold_mailer.settings import Settings
from scripts.release_metadata import resolve, windows_version
from tests.conftest import Rig

pytestmark = pytest.mark.integration


def test_encrypted_backup_roundtrip_wrong_key_tamper_and_limits(rig: Rig, tmp_path: Path) -> None:
    message = rig.message()
    target = tmp_path / "backup.cmbak"
    passphrase = "synthetic recovery passphrase"
    encrypted_backup(rig.store, target, passphrase)
    raw = target.read_bytes()
    assert raw.startswith(MAGIC)
    assert message.body.encode() not in raw and message.recipient.encode() not in raw
    destination = tmp_path / "restored.sqlite3"
    restore_encrypted(target, destination, passphrase)
    restored = Store(destination).message(message.id)
    assert restored.body == message.body and restored.status == Status.UNCERTAIN
    with pytest.raises(ValidationError):
        encrypted_backup(rig.store, target, passphrase)
    with pytest.raises(ValidationError):
        encrypted_backup(rig.store, tmp_path / "short.cmbak", "short")
    with pytest.raises(ValidationError):
        restore_encrypted(target, tmp_path / "wrong.sqlite3", "different recovery passphrase")
    assert not (tmp_path / "wrong.sqlite3").exists()
    target.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    with pytest.raises(ValidationError):
        restore_encrypted(target, tmp_path / "tampered.sqlite3", passphrase)
    target.write_bytes(b"invalid")
    with pytest.raises(ValidationError):
        restore_encrypted(target, tmp_path / "invalid.sqlite3", passphrase)


def test_support_bundle_contains_only_allowlisted_diagnostics(tmp_path: Path) -> None:
    target = tmp_path / "support.zip"
    write_support_bundle(target)
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == ["diagnostics.json"]
        data = json.loads(archive.read("diagnostics.json"))
    assert data == support_preview()
    assert set(data["runtime"]) == {
        "python",
        "platform",
        "qt",
        "sqlite",
        "sqlite_wal_fix_present",
        "journal_policy",
        "tools",
    }
    assert "rollback" in str(diagnostics()["journal_policy"])
    with pytest.raises(FileExistsError):
        write_support_bundle(target)


def test_content_hints_are_explainable_and_previews_preserve_content() -> None:
    assert len(quality_hints("", "{{ unresolved }}")) == 2
    assert len(quality_hints("s" * 79, "guaranteed " + "word " * 251 + "x" * 81)) == 4
    assert quality_hints("Hello", "A factual, short message.") == []
    assert "\n\n" in reading_preview("Subject", "\nA short body")


def test_selective_candidate_never_overwrites_and_rejects_stale_result(rig: Rig) -> None:
    message = rig.message(approved=False)
    rig.store.save_draft(
        message.id,
        message.subject,
        message.body,
        message.revision,
        instructions="Use a concise tone",
    )
    original = rig.store.message(message.id)
    seen = []

    class Generator:
        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            seen.append(prompt)
            return "Candidate", "A fresh body"

    candidate = rig.service.candidate(message.id, Generator(), Event())
    assert "concise tone" in seen[0]
    assert candidate.subject == "Candidate" and "Hi Alex" in candidate.body
    assert rig.store.message(message.id) == original

    class Stale:
        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            rig.store.edit(message.id, "Manual", "Manual content", original.revision)
            return "Stale", "Wrong content"

    with pytest.raises(ValidationError, match="stale"):
        rig.service.candidate(message.id, Stale(), Event())
    stop = Event()
    stop.set()
    with pytest.raises(ValidationError):
        rig.service.candidate(message.id, Generator(), stop)


def test_demo_rejects_nonempty_profiles_and_uses_only_synthetic_data(tmp_path: Path) -> None:
    settings = Settings(tmp_path / "profile")
    with Application(settings, demo=True) as app:
        assert not app.settings.network and not app.settings.api_key
        assert app.store.campaigns()
        assert all(
            msg.recipient.endswith("@example.invalid")
            for msg in app.store.messages(app.store.campaigns()[0]["id"])
        )
        assert DemoGenerator().generate("", {})[0]
    with pytest.raises(ValidationError), Application(settings, demo=True):
        pass


def test_release_version_validation_and_branch_metadata() -> None:
    assert windows_version("0.1.0") == "0.1.0.0"
    for value in ("0.1.0b1", "1.0", "01.0.0", "1.0.65536", "1.0.0;whoami"):
        with pytest.raises(ValueError):
            windows_version(value)
    root = Path(__file__).resolve().parents[1]
    metadata = resolve(root)
    assert len(metadata["source_sha"]) == 40 and metadata["distribution"] == "unsigned-preview"
    with pytest.raises(ValueError):
        resolve(root, "main")
    with pytest.raises(ValueError):
        resolve(root, "v1.0.0;whoami")


def test_future_schema_rejection_does_not_change_database(tmp_path: Path) -> None:
    path = tmp_path / "future.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version=999")
    conn.close()
    before = path.read_bytes()
    with pytest.raises(ValidationError):
        Store(path)
    assert path.read_bytes() == before


def test_doctor_cli_does_not_create_or_open_a_profile(tmp_path: Path, capsys) -> None:
    from cold_mailer.cli import main

    profile = tmp_path / "untouched"
    assert main(["--data-dir", str(profile), "doctor"]) == 0
    assert not profile.exists()
    assert json.loads(capsys.readouterr().out)["journal_policy"].startswith("rollback")
