from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

import pytest

from cold_mailer.domain.models import GenerationFailure, Status
from cold_mailer.infrastructure.ai import AIGenerator
from cold_mailer.settings import Settings
from tests.conftest import Rig


@pytest.mark.parametrize(
    ("code", "hint"),
    [
        (400, "capabilities"),
        (401, "permissions"),
        (402, "billing"),
        (403, "restrictions"),
        (404, "exact model ID"),
        (408, "timed out"),
        (429, "quota"),
        (500, "temporarily unavailable"),
        (503, "temporarily unavailable"),
        (504, "timed out"),
        (418, "connectivity"),
        (None, "connectivity"),
        (999, "connectivity"),
        (True, "connectivity"),
    ],
)
def test_provider_failure_is_actionable_and_does_not_expose_response(
    tmp_path: Path, monkeypatch, code: int | None, hint: str
) -> None:
    from google import genai

    class ProviderError(Exception):
        code: int | None = None

    error = ProviderError("Synthetic credential in provider response must never be displayed")
    error.code = code
    client = MagicMock()
    client.__enter__.return_value = client
    client.models.generate_content.side_effect = error
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(genai, "Client", factory)
    settings = Settings(
        tmp_path, model="models/gemini-flash-latest", api_key="fixture", network=True
    )
    with pytest.raises(GenerationFailure) as raised:
        AIGenerator(settings).generate("Synthetic facts", {"first_name": "Avery"})
    message = str(raised.value)
    assert hint in message and "Synthetic credential" not in message
    assert "No generated content was approved" in message
    assert client.models.generate_content.call_count == 1
    assert factory.call_args.kwargs["http_options"].retry_options.attempts == 1
    assert client.models.generate_content.call_args.kwargs["model"] == settings.model


@pytest.mark.parametrize("parallelism", [1, 2])
def test_safe_provider_diagnostics_reach_campaign_log_without_saving_failure_text(
    rig: Rig, parallelism: int
) -> None:
    rig.store.add_contacts(
        rig.campaign, rig.sender.id, [{"email": "a@example.com"}, {"email": "b@example.com"}]
    )
    events = []

    class Generator:
        calls = 0
        parallelism = 1

        def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
            self.calls += 1
            raise GenerationFailure(503)

    generator = Generator()
    generator.parallelism = parallelism
    summary = rig.service.generate(rig.campaign, generator, Event(), events.append)
    assert summary.failed == 2 and summary.generated == 0 and generator.calls == 2
    assert len(events) == 2 and all("HTTP 503" in event for event in events)
    assert all(
        not message.body and message.approval is None and message.status == Status.DRAFT
        for message in rig.store.messages(rig.campaign)
    )
    with rig.store.connection() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM generation_requests WHERE state='failed'"
            ).fetchone()[0]
            == 2
        )
    assert not rig.store.history() and not rig.mail.messages
