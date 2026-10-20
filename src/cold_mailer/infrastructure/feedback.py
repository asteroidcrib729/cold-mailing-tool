"""Bounded local EML review. Files never authenticate authorship or trigger sending."""

import hashlib
import re
import time
from dataclasses import dataclass, field
from datetime import UTC
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path

from cold_mailer.domain.models import ValidationError, address, identifier
from cold_mailer.infrastructure.storage import Store


@dataclass(frozen=True)
class FeedbackDocument:
    sender: str
    subject: str
    references: tuple[str, ...]
    received_utc: str | None
    sha256: str
    body: str = field(repr=False)


@dataclass(frozen=True)
class PreparedFeedback:
    message_id: str
    document: FeedbackDocument


def read_feedback(path: Path) -> FeedbackDocument:
    with path.open("rb") as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValidationError("Choose an EML file no larger than 2 MiB.")
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        if (
            not isinstance(message, EmailMessage)
            or message.defects
            or len(list(message.walk())) > 100
        ):
            raise ValueError
        senders = getaddresses(message.get_all("From", []))
        if len(senders) != 1:
            raise ValueError
        sender = address(senders[0][1])
        part = message.get_body(preferencelist=("plain",))
        body = (
            str(part.get_content())[:20_000]
            if part is not None
            else "No plain-text body. HTML and attachments were not rendered."
        )
        references = tuple(
            dict.fromkeys(
                re.findall(
                    r"<[^<>\s]{1,250}>",
                    str(message.get("In-Reply-To", "")) + " " + str(message.get("References", "")),
                )
            )
        )[:50]
        received = None
        if message.get("Date"):
            try:
                parsed = parsedate_to_datetime(str(message["Date"]))
                if parsed.tzinfo is not None:
                    received = parsed.astimezone(UTC).isoformat()
            except ValueError, TypeError, OverflowError:
                pass
        return FeedbackDocument(
            sender,
            str(message.get("Subject", ""))[:998],
            references,
            received,
            hashlib.sha256(raw).hexdigest(),
            body,
        )
    except ValueError, TypeError, LookupError, RecursionError:
        raise ValidationError(
            "This EML file is malformed or has no single valid sender. Nothing was recorded."
        ) from None


def record_feedback(store: Store, message_id: str, document: FeedbackDocument, kind: str) -> bool:
    if kind not in {"reply", "optout", "note"}:
        raise ValidationError("Choose reply, optout, or an explicitly linked operator note.")
    message = store.message(message_id)
    if kind != "note" and (
        message.recipient != document.sender or message.message_id not in document.references
    ):
        raise ValidationError(
            "Reply/opt-out linking requires both the original Message-ID and matching recipient address. Use an operator note for uncertain associations."
        )
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT message_id FROM feedback_events WHERE source_sha256=?", (document.sha256,)
        ).fetchone()
        if existing:
            if existing[0] != message_id:
                raise ValidationError("This file was already linked to a different message.")
            return False
        conn.execute(
            "INSERT INTO feedback_events VALUES (?,?,?,?,?,?,?)",
            (
                identifier(),
                message_id,
                kind,
                document.sha256,
                document.received_utc,
                time.time_ns() // 1000,
                document.body,
            ),
        )
        if kind == "optout":
            conn.execute(
                "INSERT INTO suppressions VALUES (?,'reviewed_optout') ON CONFLICT(email) DO UPDATE SET reason=excluded.reason",
                (message.recipient,),
            )
            conn.execute(
                "UPDATE messages SET status='suppressed',approval=NULL WHERE recipient=? AND status IN ('draft','approved','retryable','failed')",
                (message.recipient,),
            )
        conn.execute(
            "INSERT INTO audit_events VALUES (?,?,?,?,?)",
            (
                identifier(),
                message_id,
                "feedback_" + kind,
                time.time_ns() // 1000,
                json_detail(document),
            ),
        )
    return True


def json_detail(document: FeedbackDocument) -> str:
    import json

    return json.dumps(
        {
            "source_sha256": document.sha256,
            "association": "operator reviewed; file is not authentication evidence",
        }
    )
