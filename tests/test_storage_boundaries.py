import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from cold_mailer.domain.models import Outcome, Sender, Status, ValidationError
from cold_mailer.infrastructure.storage import Store
from tests.conftest import Rig

pytestmark = pytest.mark.integration


def test_missing_records_and_unrecognized_schema(rig: Rig, tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        rig.store.sender("missing")
    with pytest.raises(ValidationError):
        rig.store.message("missing")
    with pytest.raises(ValidationError):
        rig.store.approve("missing", 0)
    with pytest.raises(ValidationError):
        rig.store.claim("missing", 0)
    with pytest.raises(ValidationError):
        rig.store.create_campaign(" ")
    path = tmp_path / "unknown.db"
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("CREATE TABLE unknown(x)")
    with pytest.raises(ValidationError):
        Store(path)


def test_sender_history_preferences_and_campaign_configuration(rig: Rig) -> None:
    assert rig.store.preference("model", "selected") == "selected"
    rig.store.save_preference("model", "first")
    rig.store.save_preference("model", "second")
    assert rig.store.preference("model") == "second"
    rig.store.save_campaign(rig.campaign, "new prompt", "{{ AI_GENERATED_BODY }}")
    assert rig.store.campaigns()[0]["prompt"] == "new prompt"
    rig.message()
    with pytest.raises(ValidationError):
        rig.store.delete_sender(rig.sender.id)
    spare = replace(rig.sender, id="spare")
    rig.store.save_sender(spare)
    rig.store.delete_sender("spare")
    assert len(rig.store.senders()) == 1


def test_inflight_sender_edit_and_stale_claim_are_rejected(rig: Rig) -> None:
    message = rig.message()
    assert rig.store.claim(message.id, 100)
    with pytest.raises(ValidationError):
        rig.store.save_sender(replace(rig.sender, email="other@example.com"))
    assert rig.store.sender(rig.sender.id) == rig.sender


def test_approval_tampering_and_late_suppression(rig: Rig) -> None:
    message = rig.message()
    with rig.store.connection() as conn:
        conn.execute("UPDATE messages SET body='tampered' WHERE id=?", (message.id,))
    with pytest.raises(ValidationError):
        rig.store.claim(message.id, 100)
    rig.store.approve(message.id, message.revision)
    with rig.store.connection() as conn:
        conn.execute(
            "INSERT INTO suppressions VALUES (?,?)", (message.recipient, "external update")
        )
    assert rig.store.claim(message.id, 100) is None
    assert rig.store.message(message.id).status == Status.SUPPRESSED


def test_attempt_limits_pacing_and_completion_guards(rig: Rig) -> None:
    rig.store.save_sender(replace(rig.sender, interval=60))
    first, second = rig.message(), rig.message("second@example.com")
    attempt = rig.store.claim(first.id, 100)
    assert attempt
    assert rig.store.claim(second.id, 101) is None
    with pytest.raises(ValidationError):
        rig.store.finish(first.id, attempt, "invented", "bad", 101)
    with pytest.raises(ValidationError):
        rig.store.finish(first.id, "missing", "failed", "bad", 101)
    rig.store.finish(first.id, attempt, "retryable", "temporary", 101)
    assert rig.store.claim(first.id, 110) is None
    for now in (200, 300):
        attempt = rig.store.claim(first.id, now)
        assert attempt
        rig.store.finish(first.id, attempt, "retryable", "temporary", now)
    assert rig.store.claim(first.id, 400) is None


def test_acceptance_reconciliation_is_not_another_submission(rig: Rig) -> None:
    message = rig.message()
    assert rig.store.claim(message.id, 100)
    rig.store.recover()
    rig.store.reconcile(message.id, True)
    assert rig.store.message(message.id).status == Status.ACCEPTED
    assert rig.service.run(rig.campaign, Event()).accepted == 0


def test_transport_exception_is_uncertain_and_stops_batch(rig: Rig) -> None:
    from cold_mailer.application.campaigns import CampaignService
    from cold_mailer.domain.models import Message, SendResult

    first, second = rig.message(), rig.message("second@example.com")

    class Broken:
        def preflight(self) -> None:
            return None

        def send(self, sender: Sender, credential: str, message: Message) -> SendResult:
            raise RuntimeError("unexpected transport issue")

    service = CampaignService(rig.store, rig.credentials, Broken())
    assert service.run(rig.campaign, Event()).uncertain == 1
    assert rig.store.message(first.id).status == Status.UNCERTAIN
    assert rig.store.message(second.id).status == Status.APPROVED


def test_cancel_after_acceptance_does_not_undo_outcome(rig: Rig) -> None:
    stop = Event()
    first = rig.message()
    rig.message("second@example.com")
    summary = rig.service.run(rig.campaign, stop, lambda _: stop.set())
    assert summary.accepted == 1 and summary.cancelled
    assert rig.store.message(first.id).status == Status.ACCEPTED


def test_generation_missing_campaign_skips_and_pre_cancel(rig: Rig) -> None:
    class Good:
        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            return "Subject", "Body"

    with pytest.raises(ValidationError):
        rig.service.generate("missing", Good(), Event())
    rig.message()
    assert rig.service.generate(rig.campaign, Good(), Event()).skipped == 1
    stop = Event()
    stop.set()
    assert rig.service.generate(rig.campaign, Good(), stop).cancelled


def test_authentication_failure_stops_sender_batch(rig: Rig) -> None:
    rig.message()
    rig.message("second@example.com")
    rig.mail.outcome, rig.mail.code = Outcome.FAILED, "authentication_failed"
    assert rig.service.run(rig.campaign, Event()).failed == 1
    assert len(rig.mail.messages) == 1


def test_explicit_sender_rotation_is_frozen_before_approval(rig: Rig) -> None:
    second = replace(rig.sender, id="second", email="second@example.com")
    rig.store.save_sender(second)
    contacts = [{"email": f"contact{index}@example.com"} for index in range(4)]
    rig.store.add_contacts(rig.campaign, rig.sender.id, contacts, rotate=[rig.sender.id, second.id])
    assert [message.sender_id for message in rig.store.messages(rig.campaign)] == [
        rig.sender.id,
        second.id,
        rig.sender.id,
        second.id,
    ]


def test_generation_cannot_overlap_an_active_send(rig: Rig) -> None:
    from filelock import FileLock

    class Good:
        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            return "Subject", "Body"

    with FileLock(str(rig.store.path) + ".send.lock"), pytest.raises(ValidationError):
        rig.service.generate(rig.campaign, Good(), Event())
