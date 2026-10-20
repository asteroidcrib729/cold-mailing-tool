import json
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
from pathlib import Path
from threading import Event

import pytest

from cold_mailer.domain.models import Status, ValidationError
from cold_mailer.infrastructure.feedback import read_feedback, record_feedback
from cold_mailer.infrastructure.organization import GenerationBudget, Organization
from tests.conftest import Rig

pytestmark = pytest.mark.integration


def test_frozen_audience_never_expands_and_run_is_not_reused(rig: Rig) -> None:
    first, second = rig.message(), rig.message("other@example.com")
    organization = Organization(rig.store)
    run = organization.freeze(rig.campaign, [first.id])
    rig.message("new@example.com")
    assert rig.service.run(rig.campaign, Event(), run_id=run).accepted == 1
    assert [msg.id for msg in rig.mail.messages] == [first.id]
    assert rig.store.message(second.id).status == Status.APPROVED
    with pytest.raises(ValidationError):
        rig.service.run(rig.campaign, Event(), run_id=run)
    report = organization.report(rig.campaign)
    assert report["transport_attempts"] == {"accepted": 1}
    runs = report["frozen_runs"]
    assert isinstance(runs, list) and runs[0]["state"] == "finished"
    with pytest.raises(ValidationError):
        organization.freeze(rig.campaign, ["foreign-id"])


def test_changed_or_later_approved_revisions_are_excluded_from_frozen_run(rig: Rig) -> None:
    first, second = rig.message(), rig.message("other@example.com", approved=False)
    organization = Organization(rig.store)
    run = organization.freeze(rig.campaign)
    rig.store.edit(first.id, "New", "Changed content", first.revision)
    rig.store.approve(first.id, first.revision + 1)
    rig.store.approve(second.id, second.revision)
    result = rig.service.run(rig.campaign, Event(), run_id=run)
    assert result.accepted == 0 and result.skipped == 2
    assert not rig.mail.messages


def test_claim_rechecks_frozen_revision_after_admission(rig: Rig, monkeypatch) -> None:
    message = rig.message()

    def password(key: str) -> str:
        rig.store.edit(message.id, "Changed after admission", "Do not send this", message.revision)
        rig.store.approve(message.id, message.revision + 1)
        return "synthetic"

    monkeypatch.setattr(rig.credentials, "get", password)
    result = rig.service.run(rig.campaign, Event())
    assert result.skipped == 1 and not rig.mail.messages


def test_generation_budgets_are_persistent_and_atomic(rig: Rig) -> None:
    rig.store.add_contacts(
        rig.campaign,
        rig.sender.id,
        [{"email": f"p{i}@example.com", "first_name": "Person"} for i in range(3)],
    )
    rig.store.save_preference("generation.budget", json.dumps({"per_run": 1, "per_day": 2}))

    class Generator:
        parallelism = 2

        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            return "Subject", "Individual draft"

    assert rig.service.generate(rig.campaign, Generator(), Event()).generated == 1
    assert rig.service.generate(rig.campaign, Generator(), Event()).generated == 1
    assert rig.service.generate(rig.campaign, Generator(), Event()).generated == 0
    organization = Organization(rig.store)
    assert organization.available_requests() == 0
    assert organization.report(rig.campaign)["generation_requests"] == 2
    rig.store.save_preference("generation.budget", '{"per_run":10,"per_day":3}')
    message = rig.store.messages(rig.campaign)[0]

    def reserve(index: int) -> str | None:
        try:
            return organization.reserve_generation(str(index), message, "model", "brief")
        except ValidationError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sum(value is not None for value in executor.map(reserve, [1, 2])) == 1
    for raw in (
        '{"unknown":1}',
        '{"per_run":0}',
        '{"per_day":"wrong"}',
        '{"price_per_request":-1}',
        "not-json",
    ):
        rig.store.save_preference("generation.budget", raw)
        with pytest.raises(ValidationError):
            GenerationBudget.load(rig.store)


def test_restore_revision_creates_unapproved_revision_and_rejects_stale_edit(rig: Rig) -> None:
    message = rig.message()
    original = rig.store.revisions(message.id)[0]
    rig.store.edit(message.id, "New subject", "New body", message.revision)
    organization = Organization(rig.store)
    with pytest.raises(ValidationError):
        organization.restore_revision(message.id, str(original["id"]), message.revision)
    organization.restore_revision(message.id, str(original["id"]), message.revision + 1)
    restored = rig.store.message(message.id)
    assert restored.subject == message.subject and restored.approval is None
    assert rig.store.revisions(message.id)[0]["origin"] == "restored"
    with pytest.raises(ValidationError):
        organization.restore_revision(message.id, "missing", restored.revision)


def feedback_file(path: Path, message_id: str, sender: str = "alex@example.com") -> Path:
    mail = EmailMessage()
    mail["From"] = sender
    mail["To"] = "sender@example.com"
    mail["Subject"] = "Re: a reviewed message"
    mail["In-Reply-To"] = message_id
    mail["Date"] = "Tue, 20 Oct 2026 12:00:00 +0500"
    mail.set_content("Please record this local reply.")
    path.write_bytes(mail.as_bytes())
    return path


def test_feedback_linking_deduplication_and_explicit_optout(rig: Rig, tmp_path: Path) -> None:
    message = rig.message()
    path = feedback_file(tmp_path / "reply.eml", message.message_id)
    document = read_feedback(path)
    assert document.received_utc == "2026-10-20T07:00:00+00:00"
    assert record_feedback(rig.store, message.id, document, "optout")
    assert message.recipient in rig.store.suppressed()
    assert rig.store.message(message.id).status == Status.SUPPRESSED
    assert not record_feedback(rig.store, message.id, document, "optout")
    second = rig.message("other@example.com")
    with pytest.raises(ValidationError):
        record_feedback(rig.store, second.id, document, "reply")
    with pytest.raises(ValidationError):
        record_feedback(rig.store, second.id, document, "note")
    with pytest.raises(ValidationError):
        record_feedback(rig.store, message.id, document, "invented")
    assert Organization(rig.store).report(rig.campaign)["operator_reviewed_feedback"] == {
        "optout": 1
    }


def test_feedback_parser_rejects_bad_input_and_never_renders_html(rig: Rig, tmp_path: Path) -> None:
    path = tmp_path / "bad.eml"
    path.write_bytes(b"not a mail file")
    with pytest.raises(ValidationError):
        read_feedback(path)
    path.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    with pytest.raises(ValidationError):
        read_feedback(path)
    mail = EmailMessage()
    mail["From"] = "unmatched@example.com"
    mail["Date"] = "invalid"
    mail.set_content("<script>alert(1)</script>", subtype="html")
    path.write_bytes(mail.as_bytes())
    doc = read_feedback(path)
    assert doc.received_utc is None and "not rendered" in doc.body
    message = rig.message()
    with pytest.raises(ValidationError):
        record_feedback(rig.store, message.id, doc, "reply")
    assert record_feedback(rig.store, message.id, doc, "note")


def test_restart_holds_interrupted_jobs_without_resubmission(rig: Rig) -> None:
    message = rig.message()
    organization = Organization(rig.store)
    run = organization.freeze(rig.campaign)
    organization.run_messages(run, rig.campaign)
    organization.reserve_generation("job", message, "model", "brief")
    assert rig.store.recover() == 0
    with rig.store.connection() as conn:
        assert (
            conn.execute("SELECT state FROM frozen_runs WHERE id=?", (run,)).fetchone()[0]
            == "interrupted"
        )
        assert conn.execute("SELECT state FROM generation_requests").fetchone()[0] == "interrupted"
    assert not rig.mail.messages


@pytest.mark.parametrize("change", ["brief", "draft", "cancel"])
def test_serial_generation_preserves_concurrent_changes(rig: Rig, change: str) -> None:
    rig.store.add_contacts(
        rig.campaign, rig.sender.id, [{"email": "new@example.com", "first_name": "New"}]
    )
    message = rig.store.messages(rig.campaign)[0]
    stop = Event()

    class Generator:
        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            if change == "brief":
                rig.store.save_campaign(rig.campaign, "Changed brief", "{{ AI_GENERATED_BODY }}")
            elif change == "draft":
                rig.store.save_draft(message.id, "Manual subject", "Manual body", message.revision)
            else:
                stop.set()
            return "Generated", "Stale result"

    result = rig.service.generate(rig.campaign, Generator(), stop)
    assert result.generated == 0
    assert rig.store.message(message.id).body == ("Manual body" if change == "draft" else "")
    with rig.store.connection() as conn:
        assert conn.execute("SELECT state FROM generation_requests").fetchone()[0] == (
            "cancelled" if change == "cancel" else "stale"
        )
