"""Versioned SQLite storage. Each method owns its connection and short transaction."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Generator
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path

from cold_mailer.domain.models import (
    Message,
    Sender,
    Status,
    ValidationError,
    address,
    fingerprint,
    identifier,
    validate_content,
)

SCHEMA = """
CREATE TABLE senders(id TEXT PRIMARY KEY, email TEXT NOT NULL, host TEXT NOT NULL,
 port INTEGER NOT NULL, username TEXT NOT NULL, tls TEXT NOT NULL,
 daily_limit INTEGER NOT NULL, interval REAL NOT NULL);
CREATE TABLE campaigns(id TEXT PRIMARY KEY, name TEXT NOT NULL, prompt TEXT NOT NULL DEFAULT '',
 wrapper TEXT NOT NULL DEFAULT '{{ AI_GENERATED_BODY }}');
CREATE TABLE messages(id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id),
 sender_id TEXT NOT NULL REFERENCES senders(id), recipient TEXT NOT NULL, contact TEXT NOT NULL,
 subject TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft',
 revision INTEGER NOT NULL DEFAULT 0, approval TEXT, sender_email TEXT NOT NULL DEFAULT '',
 message_id TEXT NOT NULL, UNIQUE(campaign_id, recipient));
CREATE TABLE attempts(id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id),
 sender_id TEXT NOT NULL REFERENCES senders(id), started REAL NOT NULL, finished REAL,
 outcome TEXT NOT NULL, code TEXT NOT NULL DEFAULT '');
CREATE TABLE suppressions(email TEXT PRIMARY KEY, reason TEXT NOT NULL);
CREATE TABLE preferences(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX attempts_sender_time ON attempts(sender_id, started);
"""


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise ValidationError(
                    "This profile requires a newer application. No data was changed."
                )
            if version == 0:
                if connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchone():
                    raise ValidationError(
                        "Unrecognized database. Choose a new profile or explicit legacy import."
                    )
                connection.executescript(
                    "BEGIN IMMEDIATE;" + SCHEMA + "PRAGMA user_version=1; COMMIT;"
                )

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            with connection:
                yield connection
        finally:
            connection.close()

    def save_sender(self, sender: Sender) -> None:
        sender.validate()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute(
                "SELECT 1 FROM messages WHERE sender_id=? AND status='sending'", (sender.id,)
            ).fetchone():
                raise ValidationError("Cannot edit a sender while a message is in flight.")
            conn.execute(
                "INSERT INTO senders VALUES (:id,:email,:host,:port,:username,:tls,:daily_limit,:interval) ON CONFLICT(id) DO UPDATE SET email=excluded.email,host=excluded.host,port=excluded.port,username=excluded.username,tls=excluded.tls,daily_limit=excluded.daily_limit,interval=excluded.interval",
                asdict(sender),
            )
            conn.execute(
                "UPDATE messages SET status='draft',approval=NULL,revision=revision+1 WHERE sender_id=? AND status IN ('draft','approved','retryable','failed')",
                (sender.id,),
            )

    def senders(self) -> list[Sender]:
        with self.connection() as conn:
            return [
                Sender(**dict(row)) for row in conn.execute("SELECT * FROM senders ORDER BY rowid")
            ]

    def sender(self, sender_id: str) -> Sender:
        for sender in self.senders():
            if sender.id == sender_id:
                return sender
        raise ValidationError("Sender account was not found.")

    def delete_sender(self, sender_id: str) -> None:
        with self.connection() as conn:
            if conn.execute(
                "SELECT 1 FROM messages WHERE sender_id=? LIMIT 1", (sender_id,)
            ).fetchone():
                raise ValidationError("This sender has campaign history and cannot be deleted.")
            conn.execute("DELETE FROM senders WHERE id=?", (sender_id,))

    def create_campaign(
        self, name: str, prompt: str = "", wrapper: str = "{{ AI_GENERATED_BODY }}"
    ) -> str:
        if not name.strip():
            raise ValidationError("A campaign name is required.")
        campaign_id = identifier()
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO campaigns VALUES (?,?,?,?)",
                (campaign_id, name.strip(), prompt, wrapper),
            )
        return campaign_id

    def campaigns(self) -> list[dict[str, str]]:
        with self.connection() as conn:
            return [
                dict(row) for row in conn.execute("SELECT * FROM campaigns ORDER BY rowid DESC")
            ]

    def preference(self, key: str, default: str = "") -> str:
        with self.connection() as conn:
            row = conn.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def save_preference(self, key: str, value: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO preferences VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def save_campaign(self, campaign_id: str, prompt: str, wrapper: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE campaigns SET prompt=?,wrapper=? WHERE id=?", (prompt, wrapper, campaign_id)
            )

    def add_contacts(
        self,
        campaign_id: str,
        sender_id: str,
        contacts: list[dict[str, str]],
        *,
        rotate: list[str] | None = None,
    ) -> int:
        count = 0
        sender_ids = rotate or [sender_id]
        for selected in sender_ids:
            self.sender(selected)
        with self.connection() as conn:
            for index, contact in enumerate(contacts):
                recipient = address(contact["email"])
                msg_id = identifier()
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO messages(id,campaign_id,sender_id,recipient,contact,message_id) VALUES (?,?,?,?,?,?)",
                    (
                        msg_id,
                        campaign_id,
                        sender_ids[index % len(sender_ids)],
                        recipient,
                        json.dumps(contact),
                        f"<{msg_id}@coldmailer.local>",
                    ),
                )
                count += cursor.rowcount
        return count

    def messages(self, campaign_id: str) -> list[Message]:
        with self.connection() as conn:
            return [
                self._message(row)
                for row in conn.execute(
                    "SELECT * FROM messages WHERE campaign_id=? ORDER BY rowid", (campaign_id,)
                )
            ]

    def message(self, message_id: str) -> Message:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            if row is None:
                raise ValidationError("Message not found.")
            return self._message(row)

    @staticmethod
    def _message(row: sqlite3.Row) -> Message:
        values = dict(row)
        values["contact"] = json.loads(values["contact"])
        values["status"] = Status(values["status"])
        return Message(**values)

    def edit(self, message_id: str, subject: str, body: str, revision: int) -> None:
        subject, body = validate_content(subject, body)
        with self.connection() as conn:
            cursor = conn.execute(
                "UPDATE messages SET subject=?,body=?,revision=revision+1,status='draft',approval=NULL WHERE id=? AND revision=? AND status IN ('draft','approved','retryable','failed')",
                (subject, body, message_id, revision),
            )
            if cursor.rowcount != 1:
                raise ValidationError("The message changed or is locked. Reload before editing.")

    def approve(self, message_id: str, revision: int) -> None:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            if row is None:
                raise ValidationError("Message not found.")
            message = self._message(row)
            if message.revision != revision or message.status not in {
                Status.DRAFT,
                Status.APPROVED,
                Status.FAILED,
                Status.RETRYABLE,
            }:
                raise ValidationError("Reload this revision before approving.")
            validate_content(message.subject, message.body)
            sender = conn.execute(
                "SELECT email FROM senders WHERE id=?", (message.sender_id,)
            ).fetchone()
            token = fingerprint(sender[0], message.recipient, message.subject, message.body)
            conn.execute(
                "UPDATE messages SET status='approved',approval=?,sender_email=? WHERE id=?",
                (token, sender[0], message_id),
            )

    def suppress(self, email: str, reason: str = "operator") -> None:
        email = address(email)
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO suppressions VALUES (?,?) ON CONFLICT(email) DO UPDATE SET reason=excluded.reason",
                (email, reason),
            )
            conn.execute(
                "UPDATE messages SET status='suppressed',approval=NULL WHERE recipient=? AND status IN ('draft','approved','retryable','failed')",
                (email,),
            )

    def suppressed(self) -> set[str]:
        with self.connection() as conn:
            return {row[0] for row in conn.execute("SELECT email FROM suppressions")}

    def claim(self, message_id: str, now: float) -> str | None:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            if row is None:
                raise ValidationError("Message not found.")
            message = self._message(row)
            if message.status not in {Status.APPROVED, Status.RETRYABLE}:
                return None
            sender = Sender(
                **dict(
                    conn.execute(
                        "SELECT * FROM senders WHERE id=?", (message.sender_id,)
                    ).fetchone()
                )
            )
            if message.sender_email != sender.email or message.approval != fingerprint(
                sender.email, message.recipient, message.subject, message.body
            ):
                raise ValidationError("Approval no longer matches the message or sender.")
            if conn.execute(
                "SELECT 1 FROM suppressions WHERE email=?", (message.recipient,)
            ).fetchone():
                conn.execute(
                    "UPDATE messages SET status='suppressed',approval=NULL WHERE id=?",
                    (message_id,),
                )
                return None
            attempts = conn.execute(
                "SELECT COUNT(*),MAX(started) FROM attempts WHERE message_id=?", (message_id,)
            ).fetchone()
            if attempts[0] >= 3 or (message.status == Status.RETRYABLE and now - attempts[1] < 30):
                return None
            daily = conn.execute(
                "SELECT COUNT(*),MAX(started) FROM attempts WHERE sender_id=? AND started>=?",
                (sender.id, now - 86400),
            ).fetchone()
            if daily[0] >= sender.daily_limit or (
                daily[1] is not None and now - daily[1] < sender.interval
            ):
                return None
            attempt_id = identifier()
            conn.execute(
                "INSERT INTO attempts(id,message_id,sender_id,started,outcome) VALUES (?,?,?,?,?)",
                (attempt_id, message_id, sender.id, now, "sending"),
            )
            conn.execute("UPDATE messages SET status='sending' WHERE id=?", (message_id,))
            return attempt_id

    def finish(self, message_id: str, attempt_id: str, outcome: str, code: str, now: float) -> None:
        if outcome not in {"accepted", "failed", "retryable", "uncertain"}:
            raise ValidationError("Invalid transport outcome.")
        with self.connection() as conn:
            cursor = conn.execute(
                "UPDATE attempts SET outcome=?,code=?,finished=? WHERE id=? AND message_id=? AND outcome='sending'",
                (outcome, code, now, attempt_id, message_id),
            )
            if cursor.rowcount != 1:
                raise ValidationError("Attempt is no longer in flight.")
            conn.execute(
                "UPDATE messages SET status=? WHERE id=? AND status='sending'",
                (outcome, message_id),
            )

    def recover(self) -> int:
        """Only call while holding the profile process lock."""
        with self.connection() as conn:
            conn.execute(
                "UPDATE attempts SET outcome='uncertain',code='process_interrupted',finished=? WHERE outcome='sending'",
                (time.time(),),
            )
            return conn.execute(
                "UPDATE messages SET status='uncertain' WHERE status='sending'"
            ).rowcount

    def reconcile(self, message_id: str, accepted: bool) -> None:
        with self.connection() as conn:
            cursor = conn.execute(
                "UPDATE messages SET status=?,approval=NULL WHERE id=? AND status='uncertain'",
                ("accepted" if accepted else "draft", message_id),
            )
            if cursor.rowcount != 1:
                raise ValidationError("Only an uncertain message can be reconciled.")

    def backup(self, destination: Path) -> None:
        if destination.exists() or destination.resolve() == self.path:
            raise ValidationError("Choose a new backup filename.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as source, closing(sqlite3.connect(destination)) as target, target:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValidationError("Backup integrity check failed.")

    @staticmethod
    def restore(source: Path, destination: Path) -> None:
        """Restore into a NEW profile; old queued work is held uncertain, never replayed."""
        if not source.is_file() or destination.exists():
            raise ValidationError("Choose an existing backup and a new destination filename.")
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as backup:
            if (
                backup.execute("PRAGMA user_version").fetchone()[0] != 1
                or backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            ):
                raise ValidationError("Unsupported or damaged backup.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(destination)) as target, target:
                backup.backup(target)
                target.execute(
                    "UPDATE messages SET status='uncertain',approval=NULL WHERE status NOT IN ('accepted','suppressed')"
                )
                target.execute(
                    "UPDATE attempts SET outcome='uncertain',code='restored_backup' WHERE outcome='sending'"
                )
