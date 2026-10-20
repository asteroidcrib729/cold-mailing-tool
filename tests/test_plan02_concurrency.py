from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, Event, Lock

import pytest

from cold_mailer.application.campaigns import CampaignService
from cold_mailer.domain.models import ValidationError
from tests.conftest import Rig

pytestmark = pytest.mark.integration


def test_generation_overlaps_at_most_two_requests_and_commits_per_recipient(rig: Rig) -> None:
    rig.store.add_contacts(
        rig.campaign,
        rig.sender.id,
        [{"email": f"p{i}@example.com", "first_name": f"Name{i}"} for i in range(6)],
    )
    lock = Lock()
    barrier = Barrier(2)
    active, peak = 0, 0

    class Parallel:
        parallelism = 2

        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            barrier.wait(timeout=5)
            with lock:
                active -= 1
            return contact["first_name"], "Body for " + contact["email"]

    summary = rig.service.generate(rig.campaign, Parallel(), Event())
    assert summary.generated == 6 and peak == 2
    messages = rig.store.messages(rig.campaign)
    assert len({message.subject for message in messages}) == 6
    assert all(
        message.recipient in message.body and message.approval is None for message in messages
    )
    assert all(rig.store.revisions(message.id)[0]["origin"] == "generated" for message in messages)


@pytest.mark.parametrize("behavior", ["failure", "stale", "cancel", "editing"])
def test_parallel_faults_preserve_current_content(rig: Rig, behavior: str) -> None:
    rig.store.add_contacts(
        rig.campaign, rig.sender.id, [{"email": "a@example.com", "first_name": "A"}]
    )
    message = rig.store.messages(rig.campaign)[0]
    stop = Event()

    class Fault:
        parallelism = 2

        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            if behavior == "failure":
                raise ValidationError("fixture")
            if behavior == "stale":
                rig.store.save_campaign(rig.campaign, "Changed prompt", "{{ AI_GENERATED_BODY }}")
            if behavior == "editing":
                assert rig.store.hold_edit(message.id)
            if behavior == "cancel":
                stop.set()
            return "Subject", "Body"

    summary = rig.service.generate(rig.campaign, Fault(), stop)
    assert summary.generated == 0
    assert summary.cancelled if behavior == "cancel" else summary.failed == 1
    assert not rig.store.message(message.id).body


def test_pacing_wait_is_interruptible_and_account_increase_wins(rig: Rig) -> None:
    first = rig.message()
    second = rig.message("second@example.com")
    attempt = rig.store.claim(first.id, 100)
    assert attempt
    rig.store.finish(first.id, attempt, "accepted", "ok", 101, minimum_interval=5, jitter=0.5)
    rig.store.save_sender(replace(rig.sender, interval=30))
    second = rig.store.message(second.id)
    rig.store.approve(second.id, second.revision)
    assert rig.store.wait_seconds(rig.sender.id, 102) == 29
    assert rig.store.claim(second.id, 120) is None
    stop = Event()
    service = CampaignService(rig.store, rig.credentials, rig.mail, clock=lambda: 102)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(service.run, rig.campaign, stop)
        stop.set()
        assert future.result(timeout=2).cancelled
    assert not rig.mail.messages


def test_claim_and_edit_registration_have_one_winner(rig: Rig) -> None:
    message = rig.message()
    with ThreadPoolExecutor(max_workers=2) as executor:
        barrier = Barrier(2)

        def claim() -> str | None:
            barrier.wait(timeout=5)
            return rig.store.claim(message.id, 100)

        def edit() -> bool:
            barrier.wait(timeout=5)
            return rig.store.hold_edit(message.id)

        claimed = executor.submit(claim)
        edited = executor.submit(edit)
        assert bool(claimed.result(timeout=5)) != edited.result(timeout=5)
