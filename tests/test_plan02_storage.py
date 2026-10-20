import csv
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from cold_mailer.domain.models import ValidationError
from cold_mailer.infrastructure.history import export_history
from cold_mailer.infrastructure.storage import SCHEMA, Store
from tests.conftest import Rig

pytestmark = pytest.mark.integration


def test_v1_migration_preserves_legacy_unknown_snapshots(tmp_path: Path) -> None:
    path = tmp_path / "v1.sqlite3"
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(SCHEMA + "PRAGMA user_version=1;")
        conn.execute(
            "INSERT INTO senders VALUES ('s','s@example.com','smtp.example.com',587,'s','starttls',50,5)"
        )
        conn.execute("INSERT INTO campaigns VALUES ('c','Legacy','','{{ AI_GENERATED_BODY }}')")
        conn.execute(
            "INSERT INTO messages(id,campaign_id,sender_id,recipient,contact,message_id,status) VALUES ('m','c','s','r@example.com','{}','id','accepted')"
        )
        conn.execute("INSERT INTO attempts VALUES ('a','m','s',100,101,'accepted','250')")
        conn.commit()
    store = Store(path)
    row = store.history()[0]
    assert row["snapshot_known"] == 0 and row["body"] is None and row["sender_email"] is None
    assert store.message("m").created_us is None
    backups = list(tmp_path.glob("*.bak"))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    Store(path)
    assert len(list(tmp_path.glob("*.bak"))) == 1


def test_immutable_attempt_and_revision_history(rig: Rig) -> None:
    msg = rig.message()
    attempt = rig.store.claim(msg.id, 100)
    assert attempt
    rig.store.finish(msg.id, attempt, "failed", "fixture", 101)
    rig.store.edit(msg.id, "Updated", "A new draft", msg.revision)
    rig.store.save_sender(replace(rig.sender, email="new@example.com"))
    row = rig.store.history()[0]
    assert (row["body"], row["sender_email"], row["recipient"], row["subject"]) == (
        msg.body,
        rig.sender.email,
        msg.recipient,
        msg.subject,
    )
    assert row["snapshot_known"] == 1
    assert len(rig.store.revisions(msg.id)) == 2
    with rig.store.connection() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE attempts SET body='tamper'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE message_revisions SET body='tamper'")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM message_revisions")


def test_first_edit_hold_beats_claim_and_survives_restart(rig: Rig) -> None:
    msg = rig.message()
    assert rig.store.hold_edit(msg.id)
    assert rig.store.hold_edit(msg.id)
    assert rig.store.claim(msg.id, 100) is None
    with pytest.raises(ValidationError, match="editor"):
        rig.store.approve(msg.id, msg.revision)
    reopened = Store(rig.store.path)
    assert reopened.claim(msg.id, 100) is None
    rig.store.save_draft(msg.id, "", "partial", msg.revision, origin="autosave")
    rig.store.release_edit(msg.id)
    with pytest.raises(ValidationError):
        rig.store.approve(msg.id, msg.revision + 1)
    rig.store.save_draft(msg.id, "Subject", "Body", msg.revision + 1, instructions="Concise")
    rig.store.approve(msg.id, msg.revision + 2)
    assert rig.store.claim(msg.id, 101)
    assert not rig.store.hold_edit(msg.id)
    assert not rig.store.hold_edit("missing")


def test_persisted_additive_pacing_and_toggle(rig: Rig) -> None:
    rig.store.save_sender(replace(rig.sender, interval=5))
    first = rig.message()
    second = rig.message("second@example.com")
    attempt = rig.store.claim(first.id, 100)
    assert attempt
    rig.store.finish(first.id, attempt, "accepted", "ok", 102, jitter=0.75)
    reopened = Store(rig.store.path)
    assert reopened.wait_seconds(rig.sender.id, 103) == 4.75
    assert reopened.claim(second.id, 107.74) is None
    attempt2 = reopened.claim(second.id, 107.75)
    assert attempt2
    with pytest.raises(ValidationError):
        reopened.finish(second.id, attempt2, "accepted", "ok", 108, jitter=float("nan"))
    reopened.save_preference("pacing.jitter", "false")
    reopened.finish(second.id, attempt2, "accepted", "ok", 108, jitter=0.9)
    assert reopened.wait_seconds(rig.sender.id, 108) == 5


def test_history_search_export_pages_and_limits(rig: Rig, tmp_path: Path) -> None:
    msg = rig.message(approved=False)
    rig.store.edit(msg.id, "=SUM(1)", "@private body", msg.revision)
    rig.store.approve(msg.id, msg.revision + 1)
    rig.service.run(rig.campaign, Event())
    assert len(rig.store.history("PRIVATE", "accepted")) == 1
    assert not rig.store.history("nomatch")
    assert not rig.store.history(outcome="failed")
    assert not rig.store.history(offset=1)
    for limit, offset in ((0, 0), (1001, 0), (1, -1)):
        with pytest.raises(ValidationError):
            rig.store.history(limit=limit, offset=offset)
    target = tmp_path / "private.csv"
    assert export_history(rig.store, target) == 1
    with target.open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["subject"].startswith("'=") and row["body"].startswith("'@")
    assert row["started_utc"].endswith("+00:00")
    with pytest.raises(FileExistsError):
        export_history(rig.store, target)


def test_draft_limits_and_blueprint_versions(rig: Rig) -> None:
    msg = rig.message()
    for subject, body, instruction in (
        ("s" * 999, "b", None),
        ("s", "b" * 100001, None),
        ("s", "b", "i" * 10001),
    ):
        with pytest.raises(ValidationError):
            rig.store.save_draft(msg.id, subject, body, msg.revision, instructions=instruction)
    with pytest.raises(ValidationError):
        rig.store.save_blueprint(" ", "", "")
    rig.store.save_blueprint("Offer", "Fact v1", "{{ AI_GENERATED_BODY }}")
    rig.store.save_blueprint("Offer", "Fact v2", "{{ AI_GENERATED_BODY }}")
    assert [row["version"] for row in rig.store.blueprints()] == [2, 1]
    assert rig.store.campaigns()[0]["prompt"] == "A factual offer"
