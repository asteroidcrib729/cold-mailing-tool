import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest
from filelock import FileLock

from cold_mailer.bootstrap import Application
from cold_mailer.domain.models import Outcome, Status, ValidationError
from cold_mailer.infrastructure.storage import Store
from cold_mailer.settings import Settings
from tests.conftest import Rig

pytestmark = pytest.mark.integration


def test_review_send_restart_and_no_replay(rig: Rig) -> None:
    message = rig.message()
    assert rig.service.dry_run(rig.campaign) == {"approved": 1}
    assert not rig.mail.messages
    assert rig.service.run(rig.campaign, Event()).accepted == 1
    assert rig.mail.messages[0].body == message.body
    assert rig.mail.messages[0].status == Status.SENDING
    assert rig.store.message(message.id).status == Status.ACCEPTED
    reopened = Store(rig.store.path)
    assert reopened.recover() == 0
    assert rig.service.run(rig.campaign, Event()).accepted == 0
    assert len(rig.mail.messages) == 1


def test_revision_edit_invalidates_approval_and_stale_edit_rejected(rig: Rig) -> None:
    message = rig.message()
    rig.store.edit(message.id, "Edited subject", "New body", message.revision)
    assert rig.store.message(message.id).approval is None
    assert rig.service.run(rig.campaign, Event()).accepted == 0
    with pytest.raises(ValidationError):
        rig.store.edit(message.id, "Stale", "Wrong body", message.revision)
    with pytest.raises(ValidationError):
        rig.store.approve(message.id, message.revision)


def test_sender_change_invalidates_pending_approval(rig: Rig) -> None:
    message = rig.message()
    rig.store.save_sender(replace(rig.sender, email="changed@example.com"))
    assert rig.store.message(message.id).status == Status.DRAFT
    assert rig.service.run(rig.campaign, Event()).accepted == 0


def test_crash_journal_and_reconciliation(rig: Rig) -> None:
    message = rig.message()
    assert rig.store.claim(message.id, 1000)
    assert rig.store.recover() == 1
    assert rig.store.message(message.id).status == Status.UNCERTAIN
    assert rig.service.run(rig.campaign, Event()).accepted == 0
    with pytest.raises(ValidationError):
        rig.store.edit(message.id, "Edit uncertain", "body", message.revision)
    rig.store.reconcile(message.id, False)
    assert rig.store.message(message.id).status == Status.DRAFT
    rig.store.approve(message.id, message.revision)
    assert rig.service.run(rig.campaign, Event()).accepted == 1
    with pytest.raises(ValidationError):
        rig.store.reconcile(message.id, True)


@pytest.mark.parametrize("outcome", [Outcome.RETRYABLE, Outcome.FAILED, Outcome.UNCERTAIN])
def test_outcomes_are_persisted_without_automatic_replay(rig: Rig, outcome: Outcome) -> None:
    message = rig.message()
    rig.mail.outcome = outcome
    summary = rig.service.run(rig.campaign, Event())
    assert rig.store.message(message.id).status.value == outcome.value
    assert summary.accepted == 0
    rig.service.run(rig.campaign, Event())
    assert len(rig.mail.messages) == 1


def test_stop_and_suppression_prevent_new_sends(rig: Rig) -> None:
    message = rig.message()
    stop = Event()
    stop.set()
    assert rig.service.run(rig.campaign, stop).cancelled
    stop.clear()
    rig.store.suppress(message.recipient)
    assert rig.service.run(rig.campaign, stop).accepted == 0
    assert rig.store.message(message.id).status == Status.SUPPRESSED
    assert not rig.mail.messages


def test_claim_exclusive_and_daily_budget(rig: Rig) -> None:
    first = rig.message()
    second = rig.message("second@example.com")
    rig.store.save_sender(replace(rig.sender, daily_limit=1))
    first = rig.store.message(first.id)
    rig.store.approve(first.id, first.revision)
    assert rig.store.claim(first.id, 1000)
    assert rig.store.claim(first.id, 1000) is None
    rig.store.approve(second.id, rig.store.message(second.id).revision)
    assert rig.store.claim(second.id, 1001) is None


def test_unapproved_and_missing_credentials(rig: Rig) -> None:
    message = rig.message(approved=False)
    assert rig.service.run(rig.campaign, Event()).skipped == 1
    rig.store.approve(message.id, message.revision)
    rig.credentials.delete(rig.sender.id)
    with pytest.raises(ValidationError):
        rig.service.run(rig.campaign, Event())
    assert rig.store.message(message.id).status == Status.APPROVED


def test_send_lock(rig: Rig) -> None:
    rig.message()
    with FileLock(str(rig.store.path) + ".send.lock"), pytest.raises(ValidationError):
        rig.service.run(rig.campaign, Event())


def test_generation_failure_and_cancel_never_approve(rig: Rig) -> None:
    rig.store.add_contacts(
        rig.campaign, rig.sender.id, [{"email": "draft@example.com", "first_name": "Draft"}]
    )

    class Failure:
        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            raise ValidationError("fixture failure")

    assert rig.service.generate(rig.campaign, Failure(), Event()).failed == 1
    message = rig.store.messages(rig.campaign)[0]
    assert message.status == Status.DRAFT and not message.body
    stop = Event()

    class Cancel:
        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            stop.set()
            return "Subject", "Body"

    assert rig.service.generate(rig.campaign, Cancel(), stop).cancelled
    assert not rig.store.message(message.id).body


def test_successful_generation_is_rendered_but_unapproved(rig: Rig) -> None:
    rig.store.add_contacts(
        rig.campaign, rig.sender.id, [{"email": "a@example.com", "first_name": "Alex"}]
    )

    class Success:
        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            return "Subject", "Generated body"

    assert rig.service.generate(rig.campaign, Success(), Event()).generated == 1
    message = rig.store.messages(rig.campaign)[0]
    assert message.body == "Hi Alex,\nGenerated body"
    assert message.status == Status.DRAFT


def test_backup_consistent_and_schema_guard(rig: Rig, tmp_path: Path) -> None:
    rig.message()
    backup = tmp_path / "backup.sqlite3"
    rig.store.backup(backup)
    assert len(Store(backup).messages(rig.campaign)) == 1
    with pytest.raises(ValidationError):
        rig.store.backup(backup)
    with closing(sqlite3.connect(backup)) as conn, conn:
        conn.execute("PRAGMA user_version=999")
    with pytest.raises(ValidationError):
        Store(backup)


def test_profile_ownership_and_recovery(tmp_path: Path) -> None:
    settings = Settings(tmp_path / "profile")
    with Application(settings), pytest.raises(ValidationError), Application(settings):
        pass
    with Application(settings) as app:
        assert app.recovered == 0
