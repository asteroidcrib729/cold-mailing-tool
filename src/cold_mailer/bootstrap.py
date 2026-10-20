"""Explicit profile ownership; constructing imports does not open user state."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from types import TracebackType

from filelock import FileLock, Timeout

from cold_mailer.application.campaigns import CampaignService
from cold_mailer.domain.models import ValidationError
from cold_mailer.domain.ports import CredentialStore
from cold_mailer.infrastructure.credentials import OSKeyring
from cold_mailer.infrastructure.smtp import SMTPTransport
from cold_mailer.infrastructure.storage import Store
from cold_mailer.settings import Settings


class Application:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.lock = FileLock(str(settings.data_dir / "profile.lock"), timeout=0)

    def __enter__(self) -> Application:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.lock.acquire()
        except Timeout:
            raise ValidationError("This profile is already open in another application.") from None
        try:
            self.store = Store(self.settings.data_dir / "campaigns.sqlite3")
            self.recovered = self.store.recover()
            if not self.settings.model:
                self.settings = replace(self.settings, model=self.store.preference("model"))
            self.credentials: CredentialStore = OSKeyring(
                hashlib.sha256(str(self.settings.data_dir).encode()).hexdigest()
            )
            self.service = CampaignService(
                self.store, self.credentials, SMTPTransport(self.settings)
            )
            return self
        except BaseException:
            self.lock.release()
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.lock.release()
