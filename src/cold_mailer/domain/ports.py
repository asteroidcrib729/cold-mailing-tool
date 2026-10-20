"""Interfaces shared by GUI, CLI, and deterministic tests."""

from typing import Protocol

from cold_mailer.domain.models import Message, Sender, SendResult


class CredentialStore(Protocol):
    def get(self, reference: str) -> str | None: ...
    def set(self, reference: str, value: str) -> None: ...
    def delete(self, reference: str) -> None: ...


class MailTransport(Protocol):
    def preflight(self) -> None: ...
    def send(self, sender: Sender, password: str, message: Message) -> SendResult: ...


class Generator(Protocol):
    def generate(self, prompt: str, contact: dict[str, str]) -> tuple[str, str]: ...
