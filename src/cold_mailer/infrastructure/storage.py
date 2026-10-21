"""Versioned SQLite storage. Each method owns its connection and short transaction."""

from __future__ import annotations

import json
import math
import random
import sqlite3
import time
from collections.abc import Generator
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path
from threading import RLock

from cold_mailer.domain.models import (
    ImportSource,
    Message,
    Sender,
    Status,
    ValidationError,
    address,
    fingerprint,
    identifier,
    validate_content,
)
from cold_mailer.domain.scheduling import SendWindow
from cold_mailer.infrastructure.migrations import VERSION, migrate

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
        self._lock = RLock()
        self._editing: set[str] = set()
        with self.connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            existing = version != 0
            if version > VERSION:
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
                version = 1
            if version < VERSION:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValidationError("Profile integrity check failed before migration.")
                if existing:
                    # Backup before changing a recognized profile. Existing backups are retained.
                    backup = self.path.with_name(
                        self.path.name + f".before-v{VERSION}-{identifier()}.bak"
                    )
                    with closing(sqlite3.connect(backup)) as target:
                        connection.backup(target)
                migrate(connection, version)

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection]:
        with self._lock, self._connection() as connection:
            yield connection

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection]:
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
                "INSERT INTO senders VALUES (:id,:email,:host,:port,:username,:tls,:daily_limit,:interval,:provider,:subject) ON CONFLICT(id) DO UPDATE SET email=excluded.email,host=excluded.host,port=excluded.port,username=excluded.username,tls=excluded.tls,daily_limit=excluded.daily_limit,interval=excluded.interval,provider=excluded.provider,subject=excluded.subject",
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

    def hold_sender(self, sender_id: str) -> None:
        """Disconnecting never changes accepted/uncertain history or an in-flight attempt."""
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO preferences(key,value) VALUES (?,'false') ON CONFLICT(key) DO UPDATE SET value='false'",
                ("oauth.connected." + sender_id,),
            )
            conn.execute(
                "UPDATE messages SET status='draft',approval=NULL,revision=revision+1 WHERE sender_id=? AND status IN ('draft','approved','retryable','failed')",
                (sender_id,),
            )

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
        source: ImportSource | None = None,
    ) -> int:
        count = 0
        sender_ids = rotate or [sender_id]
        for selected in sender_ids:
            self.sender(selected)
        with self.connection() as conn:
            batch_id = identifier()
            if source is not None:
                source.validate()
                conn.execute(
                    "INSERT INTO import_batches(id,campaign_id,source_label,source_sha256,permission_note,reviewed,created_us) VALUES (?,?,?,?,?,?,?)",
                    (
                        batch_id,
                        campaign_id,
                        source.label.strip(),
                        source.sha256,
                        source.permission_note,
                        int(source.reviewed),
                        time.time_ns() // 1000,
                    ),
                )
            for index, contact in enumerate(contacts):
                recipient = address(contact["email"])
                msg_id = identifier()
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO messages(id,campaign_id,sender_id,recipient,contact,message_id,created_us,updated_us) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        msg_id,
                        campaign_id,
                        sender_ids[index % len(sender_ids)],
                        recipient,
                        json.dumps(contact),
                        f"<{msg_id}@coldmailer.local>",
                        time.time_ns() // 1000,
                        time.time_ns() // 1000,
                    ),
                )
                count += cursor.rowcount
                if source is not None:
                    row = conn.execute(
                        "SELECT id FROM messages WHERE campaign_id=? AND recipient=?",
                        (campaign_id, recipient),
                    ).fetchone()
                    conn.execute(
                        "INSERT OR IGNORE INTO contact_sources VALUES (?,?)", (row[0], batch_id)
                    )
            if source is not None:
                conn.execute("UPDATE import_batches SET added=? WHERE id=?", (count, batch_id))
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

    def edit(
        self, message_id: str, subject: str, body: str, revision: int, *, origin: str = "manual"
    ) -> None:
        subject, body = validate_content(subject, body)
        self.save_draft(message_id, subject, body, revision, origin=origin)

    def hold_edit(self, message_id: str) -> bool:
        """Serialize first keystroke with claim, before the debounce window."""
        with self._lock:
            if message_id in self._editing:
                return True
            with self.connection() as conn:
                cursor = conn.execute(
                    "UPDATE messages SET status='draft',approval=NULL WHERE id=? AND status IN ('draft','approved','retryable','failed')",
                    (message_id,),
                )
                if not cursor.rowcount:
                    return False
            self._editing.add(message_id)
            return True

    def release_edit(self, message_id: str) -> None:
        with self._lock:
            self._editing.discard(message_id)

    def save_draft(
        self,
        message_id: str,
        subject: str,
        body: str,
        revision: int,
        *,
        instructions: str | None = None,
        origin: str = "manual",
    ) -> None:
        # Incomplete drafts are valid storage; complete content is required for approval.
        if (
            len(subject) > 998
            or len(body) > 100_000
            or (instructions is not None and len(instructions) > 10_000)
        ):
            raise ValidationError("Draft exceeds the editor size limit.")
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if origin == "generated" and message_id in self._editing:
                raise ValidationError("Generation cannot replace an active editor's changes.")
            saved = time.time_ns() // 1000
            cursor = conn.execute(
                "UPDATE messages SET subject=?,body=?,instructions=COALESCE(?,instructions),updated_us=?,revision=revision+1,status='draft',approval=NULL WHERE id=? AND revision=? AND status IN ('draft','approved','retryable','failed')",
                (subject, body, instructions, saved, message_id, revision),
            )
            if cursor.rowcount != 1:
                raise ValidationError("The message changed or is locked. Reload before editing.")
            row = conn.execute(
                "SELECT m.*,s.email FROM messages m JOIN senders s ON m.sender_id=s.id WHERE m.id=?",
                (message_id,),
            ).fetchone()
            conn.execute(
                "INSERT INTO message_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier(),
                    message_id,
                    row["revision"],
                    subject,
                    body,
                    row["instructions"],
                    row["email"],
                    row["recipient"],
                    saved,
                    origin,
                    fingerprint(row["email"], row["recipient"], subject, body),
                ),
            )

    def approve(self, message_id: str, revision: int) -> None:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            if row is None:
                raise ValidationError("Message not found.")
            message = self._message(row)
            if message_id in self._editing:
                raise ValidationError("Save or discard editor changes before approving.")
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

    def claim(
        self, message_id: str, now: float, *, minimum_interval: float = 0, run_id: str | None = None
    ) -> str | None:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            if row is None:
                raise ValidationError("Message not found.")
            message = self._message(row)
            if run_id is not None:
                selection = conn.execute(
                    "SELECT r.revision,r.approval,f.state FROM run_messages r JOIN frozen_runs f ON f.id=r.run_id WHERE r.run_id=? AND r.message_id=?",
                    (run_id, message_id),
                ).fetchone()
                if (
                    selection is None
                    or selection[0] != message.revision
                    or selection[1] != message.approval
                    or selection[2] != "running"
                ):
                    return None
            if message_id in self._editing:
                return None
            if message.status not in {Status.APPROVED, Status.RETRYABLE}:
                return None
            policy = conn.execute(
                "SELECT value FROM preferences WHERE key='sending.window'"
            ).fetchone()
            if not SendWindow.load(policy[0] if policy else "{}").allows(message.contact, now):
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
            schedule = conn.execute(
                "SELECT due,finished FROM schedule_state WHERE sender_id=?", (sender.id,)
            ).fetchone()
            if schedule and now < max(
                schedule[0], schedule[1] + max(sender.interval, minimum_interval)
            ):
                return None
            attempt_id = identifier()
            conn.execute(
                "INSERT INTO attempts(id,message_id,sender_id,started,outcome,sender_email,recipient,subject,body,revision,content_hash,snapshot_known,run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)",
                (
                    attempt_id,
                    message_id,
                    sender.id,
                    now,
                    "sending",
                    sender.email,
                    message.recipient,
                    message.subject,
                    message.body,
                    message.revision,
                    message.approval,
                    run_id,
                ),
            )
            conn.execute("UPDATE messages SET status='sending' WHERE id=?", (message_id,))
            return attempt_id

    def finish(
        self,
        message_id: str,
        attempt_id: str,
        outcome: str,
        code: str,
        now: float,
        *,
        jitter: float | None = None,
        minimum_interval: float = 0,
    ) -> None:
        if outcome not in {"accepted", "failed", "retryable", "uncertain"}:
            raise ValidationError("Invalid transport outcome.")
        if jitter is not None and (not math.isfinite(jitter) or not 0 <= jitter < 1):
            raise ValidationError("Jitter must be in [0, 1).")
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
            sender = conn.execute(
                "SELECT s.id,s.interval FROM senders s JOIN messages m ON m.sender_id=s.id WHERE m.id=?",
                (message_id,),
            ).fetchone()
            enabled = self.preference("pacing.jitter", "true") == "true"
            base = max(sender["interval"], minimum_interval)
            # This is non-secret timing noise, never a token or cryptographic input.
            extra = (random.random() if jitter is None else jitter) if enabled and base > 0 else 0.0  # nosec B311
            conn.execute(
                "INSERT INTO schedule_state VALUES (?,?,?,?,?,?) ON CONFLICT(sender_id) DO UPDATE SET attempt_id=excluded.attempt_id,finished=excluded.finished,base=excluded.base,jitter=excluded.jitter,due=excluded.due",
                (sender["id"], attempt_id, now, base, extra, now + base + extra),
            )

    def wait_seconds(self, sender_id: str, now: float, *, minimum_interval: float = 0) -> float:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT p.due,p.finished,s.interval FROM schedule_state p JOIN senders s ON s.id=p.sender_id WHERE p.sender_id=?",
                (sender_id,),
            ).fetchone()
            return (
                max(0.0, max(row[0], row[1] + max(row[2], minimum_interval)) - now) if row else 0.0
            )

    def history(
        self,
        query: str = "",
        outcome: str = "",
        *,
        limit: int = 100,
        offset: int = 0,
        since: float | None = None,
        until: float | None = None,
    ) -> list[dict[str, object]]:
        if not 1 <= limit <= 1000 or offset < 0:
            raise ValidationError("History page size must be 1-1000 and offset nonnegative.")
        if any(value is not None and not math.isfinite(value) for value in (since, until)) or (
            since is not None and until is not None and since >= until
        ):
            raise ValidationError("Choose a finite history range with the end after the start.")
        clauses, parameters = [], []
        if outcome:
            clauses.append("a.outcome=?")
            parameters.append(outcome)
        if query:
            clauses.append(
                "instr(lower(COALESCE(a.subject,'') || ' ' || COALESCE(a.recipient,'') || ' ' || COALESCE(a.sender_email,'') || ' ' || COALESCE(a.body,'')),lower(?))>0"
            )
            parameters.append(query)
        if since is not None:
            clauses.append("a.started>=?")
            parameters.append(since)
        if until is not None:
            clauses.append("a.started<?")
            parameters.append(until)
        sql = "SELECT a.*,c.name AS campaign FROM attempts a JOIN messages m ON m.id=a.message_id JOIN campaigns c ON c.id=m.campaign_id"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY a.started DESC,a.id LIMIT ? OFFSET ?"
        parameters.extend((limit, offset))
        # Search readers must not hold the Store's writer lock.
        with closing(
            sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=0.25)
        ) as conn:
            conn.row_factory = sqlite3.Row
            deadline = time.monotonic() + 0.5
            conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            return [dict(row) for row in conn.execute(sql, parameters)]

    def revisions(self, message_id: str) -> list[dict[str, object]]:
        with self.connection() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM message_revisions WHERE message_id=? ORDER BY saved_us DESC,rowid DESC",
                    (message_id,),
                )
            ]

    def save_blueprint(self, name: str, prompt: str, wrapper: str) -> str:
        if not name.strip() or len(name) > 120:
            raise ValidationError("Use a blueprint name of 1-120 characters.")
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            version = conn.execute(
                "SELECT COALESCE(MAX(version),0)+1 FROM blueprints WHERE name=?", (name.strip(),)
            ).fetchone()[0]
            key = identifier()
            conn.execute(
                "INSERT INTO blueprints VALUES (?,?,?,?,?,?)",
                (key, name.strip(), version, prompt, wrapper, time.time_ns() // 1000),
            )
            return key

    def blueprints(self) -> list[dict[str, object]]:
        with self.connection() as conn:
            return [
                dict(row)
                for row in conn.execute("SELECT * FROM blueprints ORDER BY name,version DESC")
            ]

    def recover(self) -> int:
        """Only call while holding the profile process lock."""
        with self.connection() as conn:
            conn.execute(
                "UPDATE frozen_runs SET state='interrupted',finished_us=? WHERE state='running'",
                (time.time_ns() // 1000,),
            )
            conn.execute(
                "UPDATE generation_requests SET state='interrupted',finished_us=? WHERE state='requested'",
                (time.time_ns() // 1000,),
            )
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
            conn.execute(
                "INSERT INTO audit_events VALUES (?,?,?,?,?)",
                (
                    identifier(),
                    message_id,
                    "reconciled",
                    time.time_ns() // 1000,
                    json.dumps({"operator_confirmed_accepted": accepted}),
                ),
            )

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
                backup.execute("PRAGMA user_version").fetchone()[0] not in range(1, VERSION + 1)
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
                if target.execute("PRAGMA user_version").fetchone()[0] >= 3:
                    target.execute(
                        "UPDATE frozen_runs SET state='restored_hold' WHERE state IN ('prepared','running')"
                    )
                    target.execute(
                        "UPDATE generation_requests SET state='restored_hold' WHERE state='requested'"
                    )
