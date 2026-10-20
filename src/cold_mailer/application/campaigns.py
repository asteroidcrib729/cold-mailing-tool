"""One persistent campaign engine for GUI, CLI, and injected fake providers."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from threading import Event

from filelock import FileLock, Timeout

from cold_mailer.domain.models import (
    GenerationFailure,
    Message,
    Outcome,
    RunSummary,
    Status,
    ValidationError,
    identifier,
)
from cold_mailer.domain.ports import CredentialStore, Generator, MailTransport
from cold_mailer.infrastructure.organization import Organization
from cold_mailer.infrastructure.storage import Store
from cold_mailer.infrastructure.templates import render_template


@dataclass(frozen=True)
class GenerationCandidate:
    message_id: str
    revision: int
    subject: str
    body: str


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
        self.organization = Organization(store)

    def _generate_content(
        self, run_id: str, message: Message, generator: Generator, prompt: str, wrapper: str
    ) -> tuple[str, str, str]:
        model = getattr(getattr(generator, "settings", None), "model", "synthetic")
        request_id = self.organization.reserve_generation(
            run_id,
            message,
            model if isinstance(model, str) else "unspecified",
            prompt + "\n" + wrapper,
        )
        try:
            subject, body = generator.generate(prompt, message.contact)
            final = render_template(wrapper, {**message.contact, "AI_GENERATED_BODY": body})
        except Exception:
            self.organization.finish_generation(request_id, "failed")
            raise
        self.organization.finish_generation(request_id, "completed")
        return subject, final, request_id

    def candidate(self, message_id: str, generator: Generator, stop: Event) -> GenerationCandidate:
        with FileLock(str(self.store.path) + ".send.lock", timeout=0):
            message = self.store.message(message_id)
            if (
                message.status
                not in {Status.DRAFT, Status.APPROVED, Status.RETRYABLE, Status.FAILED}
                or stop.is_set()
            ):
                raise ValidationError("This message cannot be regenerated now.")
            campaign = next(
                row for row in self.store.campaigns() if row["id"] == message.campaign_id
            )
            prompt = campaign["prompt"] + (
                "\nRecipient preferences:\n" + message.instructions if message.instructions else ""
            )
            subject, final, request_id = self._generate_content(
                identifier(), message, generator, prompt, campaign["wrapper"]
            )
            if (
                stop.is_set()
                or self.store.message(message_id).revision != message.revision
                or campaign
                != next(row for row in self.store.campaigns() if row["id"] == message.campaign_id)
            ):
                self.organization.finish_generation(request_id, "stale")
                raise ValidationError(
                    "Generation became stale or was cancelled. Current content was preserved."
                )
            return GenerationCandidate(message_id, message.revision, subject, final)

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
        if getattr(generator, "parallelism", 1) == 2:
            return self._parallel_generate(campaign_id, campaign, generator, stop, emit)
        summary = RunSummary()
        run_id, available = identifier(), self.organization.available_requests()
        for message in self.store.messages(campaign_id):
            if stop.is_set():
                summary.cancelled = True
                break
            if message.status != Status.DRAFT or message.body:
                summary.skipped += 1
                continue
            if summary.generated + summary.failed >= available:
                summary.skipped += 1
                continue
            try:
                prompt = campaign["prompt"] + (
                    "\nRecipient preferences:\n" + message.instructions
                    if message.instructions
                    else ""
                )
                subject, final, request_id = self._generate_content(
                    run_id, message, generator, prompt, campaign["wrapper"]
                )
                if stop.is_set():
                    self.organization.finish_generation(request_id, "cancelled")
                    summary.cancelled = True
                    break
                try:
                    if campaign != next(
                        row for row in self.store.campaigns() if row["id"] == campaign_id
                    ):
                        raise ValidationError("Campaign instructions changed during generation.")
                    self.store.edit(
                        message.id, subject, final, message.revision, origin="generated"
                    )
                except ValidationError:
                    self.organization.finish_generation(request_id, "stale")
                    raise
                summary.generated += 1
                emit("Draft generated; review and approve before sending.")
            except ValidationError as exc:
                summary.failed += 1
                emit(
                    str(exc)
                    if isinstance(exc, GenerationFailure)
                    else "Generation failed for a draft; it remains unapproved."
                )
        return summary

    def _parallel_generate(
        self,
        campaign_id: str,
        campaign: dict[str, str],
        generator: Generator,
        stop: Event,
        emit: Callable[[str], None],
    ) -> RunSummary:
        summary = RunSummary()
        messages = self.store.messages(campaign_id)
        eligible = [
            message for message in messages if message.status == Status.DRAFT and not message.body
        ]
        summary.skipped = len(messages) - len(eligible)
        available = self.organization.available_requests()
        summary.skipped += max(0, len(eligible) - available)
        eligible = eligible[:available]
        run_id = identifier()

        def produce(message: Message) -> tuple[Message, str, str, str] | GenerationFailure | None:
            if stop.is_set():
                return None
            try:
                prompt = campaign["prompt"] + (
                    "\nRecipient preferences:\n" + message.instructions
                    if message.instructions
                    else ""
                )
                subject, body, request_id = self._generate_content(
                    run_id, message, generator, prompt, campaign["wrapper"]
                )
                return (
                    message,
                    subject,
                    body,
                    request_id,
                )
            except GenerationFailure as exc:
                return exc
            except ValidationError:
                return None

        # Python 3.14 buffersize bounds queued work as well as running requests.
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="ai-generation") as executor:
            for result in executor.map(produce, eligible, buffersize=2):
                if stop.is_set():
                    summary.cancelled = True
                    break
                if result is None:
                    summary.failed += 1
                    emit("Generation failed for a draft; it remains unapproved.")
                    continue
                if isinstance(result, GenerationFailure):
                    summary.failed += 1
                    emit(str(result))
                    continue
                message, subject, body, request_id = result
                try:
                    current = next(
                        row for row in self.store.campaigns() if row["id"] == campaign_id
                    )
                    if current != campaign:
                        raise ValidationError("Campaign instructions changed during generation.")
                    self.store.edit(message.id, subject, body, message.revision, origin="generated")
                    summary.generated += 1
                    emit("Draft generated; review and approve before sending.")
                except ValidationError:
                    self.organization.finish_generation(request_id, "stale")
                    summary.failed += 1
                    emit("Draft changed while generating; current edits were preserved.")
        summary.cancelled = stop.is_set()
        return summary

    def run(
        self,
        campaign_id: str,
        stop: Event,
        emit: Callable[[str], None] = lambda _: None,
        *,
        run_id: str | None = None,
        message_ids: list[str] | None = None,
    ) -> RunSummary:
        self.transport.preflight()
        try:
            with FileLock(str(self.store.path) + ".send.lock", timeout=0):
                selected = run_id or self.organization.freeze(campaign_id, message_ids)
                messages = self.organization.run_messages(selected, campaign_id)
                try:
                    summary = self._run(campaign_id, stop, emit, selected, messages)
                except Exception:
                    self.organization.finish_run(selected, {}, "failed")
                    raise
                self.organization.finish_run(
                    selected, asdict(summary), "cancelled" if summary.cancelled else "finished"
                )
                return summary
        except Timeout:
            raise ValidationError("A send operation already owns this profile.") from None

    def _run(
        self,
        campaign_id: str,
        stop: Event,
        emit: Callable[[str], None],
        run_id: str,
        messages: list[Message],
    ) -> RunSummary:
        summary = RunSummary()
        summary.skipped = self.organization.frozen_size(run_id) - len(messages)
        for message in messages:
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
            floor = float(getattr(self.transport, "minimum_interval", 0))
            delay = self.store.wait_seconds(sender.id, self.clock(), minimum_interval=floor)
            if delay and stop.wait(delay):
                summary.cancelled = True
                break
            attempt_id = self.store.claim(
                message.id, self.clock(), minimum_interval=floor, run_id=run_id
            )
            if attempt_id is None:
                summary.skipped += 1
                emit(
                    "Message skipped: suppression, changed revision, sending window, attempt budget, pacing, or daily limit."
                )
                continue
            try:
                result = self.transport.send(
                    self.store.sender(message.sender_id), password, self.store.message(message.id)
                )
            except Exception:
                self.store.finish(
                    message.id,
                    attempt_id,
                    "uncertain",
                    "unexpected_transport_error",
                    self.clock(),
                    minimum_interval=floor,
                )
                summary.uncertain += 1
                emit("Transport interrupted; outcome is uncertain. Sending stopped.")
                break
            self.store.finish(
                message.id,
                attempt_id,
                result.outcome,
                result.code,
                self.clock(),
                minimum_interval=floor,
            )
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
            if stop.is_set():
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
