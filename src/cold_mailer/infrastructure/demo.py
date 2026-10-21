"""Synthetic rehearsal adapters. Neither imports nor calls a network provider."""

from cold_mailer.domain.models import Message, Outcome, Sender, SendResult
from cold_mailer.infrastructure.credentials import MemoryCredentials
from cold_mailer.infrastructure.storage import Store


class DemoGenerator:
    parallelism = 2

    def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]:
        name = contact.get("first_name", "there")
        return (
            f"A demonstration for {name}",
            f"This is a synthetic draft for {name}. Edit it, save it, and approve it to rehearse the workflow. No email will be transmitted.",
        )


class DemoTransport:
    def preflight(self) -> None:
        pass

    def send(self, sender: Sender, credential: str, message: Message) -> SendResult:
        return SendResult(Outcome.ACCEPTED, "demo_simulated_no_transmission")


def populate(store: Store, credentials: MemoryCredentials) -> None:
    sender = Sender(
        "demo-sender", "demo@example.invalid", "smtp.example.invalid", 587, "demo", interval=0
    )
    store.save_sender(sender)
    credentials.set(sender.id, "synthetic-demo-only")
    campaign = store.create_campaign(
        "Demo · no real delivery",
        "Explain a fictional scheduling tool.",
        "Hi {{ first_name }},\n\n{{ AI_GENERATED_BODY }}\n\nDemo team",
    )
    store.add_contacts(
        campaign,
        sender.id,
        [
            {
                "email": f"person{i}@example.invalid",
                "first_name": name,
                "company": "Fictional Company",
            }
            for i, name in enumerate(("Alex", "Taylor", "Morgan", "Sam", "Jordan"))
        ],
    )
