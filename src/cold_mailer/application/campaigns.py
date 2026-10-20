"""One persistent campaign engine for GUI, CLI, and injected fake providers."""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Event

from filelock import FileLock, Timeout

from cold_mailer.domain.models import Outcome, RunSummary, Status, ValidationError
from cold_mailer.domain.ports import CredentialStore, Generator, MailTransport
from cold_mailer.infrastructure.storage import Store
from cold_mailer.infrastructure.templates import render_template


class CampaignService:
    def __init__(
        self,
        store: Store,
        credentials: CredentialStore,
        transport: MailTransport,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.store, self.credentials, self.transport, self.clock = (
            store,
            credentials,
            transport,
            clock,
        )

    def generate(
        self,
        campaign_id: str,
        generator: Generator,
        stop: Event,
        emit: Callable[[str], None] = lambda _: None,
    ) -> RunSummary:
        try:
            with FileLock(str(self.store.path) + ".send.lock", timeout=0):
                return self._generate(campaign_id, generator, stop, emit)
        except Timeout:
            raise ValidationError("Another operation already owns this profile.") from None

    def _generate(
        self,
        campaign_id: str,
        generator: Generator,
        stop: Event,
        emit: Callable[[str], None] = lambda _: None,
    ) -> RunSummary:
        campaign = next((row for row in self.store.campaigns() if row["id"] == campaign_id), None)
        if campaign is None:
            raise ValidationError("Campaign not found.")
        summary = RunSummary()
        for message in self.store.messages(campaign_id):
            if stop.is_set():
                summary.cancelled = True
                break
            if message.status != Status.DRAFT or message.body:
                summary.skipped += 1
                continue
            try:
                subject, body = generator.generate(campaign["prompt"], message.contact)
                if stop.is_set():
                    summary.cancelled = True
                    break
                final = render_template(
                    campaign["wrapper"], {**message.contact, "AI_GENERATED_BODY": body}
                )
                self.store.edit(message.id, subject, final, message.revision)
                summary.generated += 1
                emit("Draft generated; review and approve before sending.")
            except ValidationError:
                summary.failed += 1
                emit("Generation failed for a draft; it remains unapproved.")
        return summary

    def run(
        self, campaign_id: str, stop: Event, emit: Callable[[str], None] = lambda _: None
    ) -> RunSummary:
        self.transport.preflight()
        try:
            with FileLock(str(self.store.path) + ".send.lock", timeout=0):
                return self._run(campaign_id, stop, emit)
        except Timeout:
            raise ValidationError("A send operation already owns this profile.") from None

    def _run(self, campaign_id: str, stop: Event, emit: Callable[[str], None]) -> RunSummary:
        summary = RunSummary()
        for message in self.store.messages(campaign_id):
            if stop.is_set():
                summary.cancelled = True
                break
            if message.status not in {Status.APPROVED, Status.RETRYABLE}:
                summary.skipped += 1
                continue
            sender = self.store.sender(message.sender_id)
            password = self.credentials.get(sender.id)
            if not password:
                raise ValidationError(
                    "Sender credentials are missing. Re-enter them in sender settings."
                )
            attempt_id = self.store.claim(message.id, self.clock())
            if attempt_id is None:
                summary.skipped += 1
                emit("Message skipped: suppression, attempt budget, pacing, or daily limit.")
                continue
            try:
                result = self.transport.send(
                    self.store.sender(message.sender_id), password, self.store.message(message.id)
                )
            except Exception:
                self.store.finish(
                    message.id, attempt_id, "uncertain", "unexpected_transport_error", self.clock()
                )
                summary.uncertain += 1
                emit("Transport interrupted; outcome is uncertain. Sending stopped.")
                break
            self.store.finish(message.id, attempt_id, result.outcome, result.code, self.clock())
            if result.outcome == Outcome.ACCEPTED:
                summary.accepted += 1
            elif result.outcome == Outcome.RETRYABLE:
                summary.retryable += 1
            elif result.outcome == Outcome.UNCERTAIN:
                summary.uncertain += 1
            else:
                summary.failed += 1
            emit(f"Message outcome: {result.outcome} ({result.code}).")
            if result.outcome == Outcome.UNCERTAIN or result.code == "authentication_failed":
                break
            if stop.wait(sender.interval):
                summary.cancelled = True
                break
        return summary

    def dry_run(self, campaign_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for message in self.store.messages(campaign_id):
            key = (
                "suppressed"
                if message.recipient in self.store.suppressed()
                else message.status.value
            )
            counts[key] = counts.get(key, 0) + 1
        return counts
