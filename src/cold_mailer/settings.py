"""Explicit settings construction; imports never read .env or write application state."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_data_path

from cold_mailer.domain.models import ValidationError

VERSION = "0.1.0"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    model: str = ""
    api_key: str = field(default="", repr=False)
    network: bool = False
    timeout: float = 30

    @classmethod
    def load(
        cls, data_dir: Path | None = None, *, development: bool = False, network: bool = False
    ) -> Settings:
        if development:
            from dotenv import load_dotenv

            load_dotenv(Path.cwd() / ".env", override=False)
        return cls(
            data_dir=(data_dir or user_data_path("ColdMailer", "ColdMailer")).resolve(),
            model=os.getenv("GENAI_MODEL", "").strip(),
            api_key=(
                os.getenv("GOOGLE_GENAI_API_KEY")
                or (os.getenv("API_KEY", "") if development else "")
            ),
            network=network,
        )

    def require_network(self) -> None:
        if not self.network:
            raise ValidationError("Network access is disabled. Enable live mode explicitly.")
