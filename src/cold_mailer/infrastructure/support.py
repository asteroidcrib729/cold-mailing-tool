"""Allowlisted support bundles; no paths, account identifiers, content, or credentials."""

import json
import zipfile
from pathlib import Path

from cold_mailer.infrastructure.doctor import diagnostics
from cold_mailer.settings import VERSION


def support_preview() -> dict[str, object]:
    return {
        "application_version": VERSION,
        "runtime": diagnostics(),
        "contains": [
            "Application version",
            "Python / Qt / SQLite versions",
            "Tool availability flags",
        ],
        "excludes": [
            "Profiles and paths",
            "Messages and contacts",
            "Logs",
            "Passwords and API keys",
        ],
    }


def write_support_bundle(destination: Path) -> None:
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostics.json", json.dumps(support_preview(), indent=2))
