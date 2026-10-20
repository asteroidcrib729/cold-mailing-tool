"""All tests use isolated profiles, fake credentials, and denied external sockets."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from cold_mailer.application.campaigns import CampaignService
from cold_mailer.domain.models import Message, Outcome, Sender, SendResult
from cold_mailer.infrastructure.credentials import MemoryCredentials
from cold_mailer.infrastructure.storage import Store

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@dataclass
class FakeMail:
    outcome: Outcome = Outcome.ACCEPTED
    code: str = "fixture"
    messages: list[Message] = field(default_factory=list)

    def preflight(self) -> None:
        return None

    def send(self, sender: Sender, password: str, message: Message) -> SendResult:
        self.messages.append(message)
        return SendResult(self.outcome, self.code)


@dataclass
class Rig:
    store: Store
    credentials: MemoryCredentials
    sender: Sender
    campaign: str
    mail: FakeMail
    service: CampaignService

    def message(self, email: str = "alex@example.com", *, approved: bool = True) -> Message:
        self.store.add_contacts(
            self.campaign, self.sender.id, [{"email": email, "first_name": "Alex"}]
        )
        message = next(msg for msg in self.store.messages(self.campaign) if msg.recipient == email)
        self.store.edit(message.id, "A clear subject", "A reviewed final body.", message.revision)
        message = self.store.message(message.id)
        if approved:
            self.store.approve(message.id, message.revision)
        return self.store.message(message.id)


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    store = Store(tmp_path / "profile" / "campaigns.sqlite3")
    sender = Sender("sender", "sender@example.com", "smtp.example.com", 587, "sender", interval=0)
    store.save_sender(sender)
    credentials = MemoryCredentials()
    credentials.set(sender.id, "synthetic-password")
    campaign = store.create_campaign(
        "Synthetic campaign", "A factual offer", "Hi {{ first_name }},\n{{ AI_GENERATED_BODY }}"
    )
    mail = FakeMail()
    return Rig(
        store, credentials, sender, campaign, mail, CampaignService(store, credentials, mail)
    )
