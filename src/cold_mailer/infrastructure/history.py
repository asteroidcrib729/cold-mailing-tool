"""Explicit exports of private mail history, with spreadsheet formula protection."""

import csv
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from cold_mailer.domain.models import ValidationError
from cold_mailer.infrastructure.storage import Store


def utc_time(value: object) -> str:
    return (
        datetime.fromtimestamp(float(str(value)), UTC).isoformat()
        if value is not None
        else "Unknown"
    )


def safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else text


def export_history(
    store: Store,
    destination: Path,
    query: str = "",
    outcome: str = "",
    *,
    since: float | None = None,
    until: float | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> int:
    count = 0
    if destination.exists():
        raise FileExistsError("Choose a new history export filename.")
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            dir=destination.parent,
            prefix="mail-export-",
            suffix=".partial",
            delete=False,
            newline="",
            encoding="utf-8-sig",
        ) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream)
            fields = [
                "id",
                "campaign",
                "sender_email",
                "recipient",
                "subject",
                "body",
                "outcome",
                "code",
                "started_utc",
                "finished_utc",
                "snapshot_known",
            ]
            writer.writerow(fields)
            while True:
                if cancelled and cancelled():
                    raise ValidationError("History export cancelled; no final file was created.")
                rows = store.history(
                    query, outcome, limit=500, offset=count, since=since, until=until
                )
                if not rows:
                    break
                for row in rows:
                    row["started_utc"], row["finished_utc"] = (
                        utc_time(row["started"]),
                        utc_time(row["finished"]),
                    )
                    writer.writerow([safe_cell(row.get(key)) for key in fields])
                count += len(rows)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "nt":
            temporary.rename(destination)  # Windows rename refuses an existing destination.
        else:
            os.link(temporary, destination)  # Atomic exclusive publication; never overwrite.
        return count
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
