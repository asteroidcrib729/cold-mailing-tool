"""Profile-scoped provenance, frozen audiences, generation reservations and honest reports."""

import hashlib
import json
import time
from dataclasses import dataclass

from cold_mailer.domain.models import Message, ValidationError, identifier
from cold_mailer.infrastructure.storage import Store


@dataclass(frozen=True)
class GenerationBudget:
    per_run: int = 100
    per_day: int = 500
    price_per_request: float = 0.0

    @classmethod
    def load(cls, store: Store) -> GenerationBudget:
        try:
            data = json.loads(store.preference("generation.budget", "{}"))
            value = cls(**data)
            if (
                type(value.per_run) is not int
                or type(value.per_day) is not int
                or not 1 <= value.per_run <= 10_000
                or not 1 <= value.per_day <= 10_000
                or not 0 <= value.price_per_request <= 1000
            ):
                raise ValueError
            return value
        except ValueError, TypeError:
            raise ValidationError(
                "Generation budget settings are invalid. Review them in Campaign tools."
            ) from None


class Organization:
    def __init__(self, store: Store) -> None:
        self.store = store

    def sources(self, message_id: str) -> list[dict[str, object]]:
        with self.store.connection() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT b.* FROM import_batches b JOIN contact_sources c ON c.batch_id=b.id WHERE c.message_id=? ORDER BY b.created_us DESC",
                    (message_id,),
                )
            ]

    def freeze(self, campaign_id: str, message_ids: list[str] | None = None) -> str:
        with self.store.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT id,revision,approval FROM messages WHERE campaign_id=? ORDER BY rowid",
                (campaign_id,),
            ).fetchall()
            selected = set(message_ids) if message_ids is not None else {row["id"] for row in rows}
            if selected - {row["id"] for row in rows}:
                raise ValidationError(
                    "The selected audience contains recipients outside this campaign."
                )
            key = identifier()
            conn.execute(
                "INSERT INTO frozen_runs(id,campaign_id,created_us,state) VALUES (?,?,?,'prepared')",
                (key, campaign_id, time.time_ns() // 1000),
            )
            conn.executemany(
                "INSERT INTO run_messages VALUES (?,?,?,?)",
                [
                    (key, row["id"], row["revision"], row["approval"])
                    for row in rows
                    if row["id"] in selected
                ],
            )
            return key

    def run_messages(self, run_id: str, campaign_id: str) -> list[Message]:
        with self.store.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT campaign_id,state FROM frozen_runs WHERE id=?", (run_id,)
            ).fetchone()
            if row is None or row[0] != campaign_id or row[1] != "prepared":
                raise ValidationError(
                    "This frozen run is missing, already used, or belongs to another campaign."
                )
            conn.execute("UPDATE frozen_runs SET state='running' WHERE id=?", (run_id,))
            return [
                self.store._message(record)
                for record in conn.execute(
                    "SELECT m.* FROM run_messages r JOIN messages m ON m.id=r.message_id WHERE r.run_id=? AND m.revision=r.revision AND m.approval IS r.approval ORDER BY m.rowid",
                    (run_id,),
                )
            ]

    def finish_run(self, run_id: str, summary: dict[str, object], state: str = "finished") -> None:
        with self.store.connection() as conn:
            conn.execute(
                "UPDATE frozen_runs SET state=?,finished_us=?,summary=? WHERE id=? AND state IN ('prepared','running')",
                (state, time.time_ns() // 1000, json.dumps(summary), run_id),
            )

    def frozen_size(self, run_id: str) -> int:
        with self.store.connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM run_messages WHERE run_id=?", (run_id,)
            ).fetchone()[0]

    def reserve_generation(self, run_id: str, message: Message, model: str, brief: str) -> str:
        policy = GenerationBudget.load(self.store)
        now = time.time_ns() // 1000
        with self.store.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            count = conn.execute(
                "SELECT COUNT(*) FROM generation_requests WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            daily = conn.execute(
                "SELECT COUNT(*) FROM generation_requests WHERE created_us>=?",
                (now - 86_400_000_000,),
            ).fetchone()[0]
            if count >= policy.per_run or daily >= policy.per_day:
                raise ValidationError(
                    "Generation request budget reached. Review the limits before making more requests."
                )
            key = identifier()
            conn.execute(
                "INSERT INTO generation_requests(id,run_id,campaign_id,message_id,model,brief_hash,revision,state,created_us) VALUES (?,?,?,?,?,?,?,'requested',?)",
                (
                    key,
                    run_id,
                    message.campaign_id,
                    message.id,
                    model[:200],
                    hashlib.sha256(brief.encode()).hexdigest(),
                    message.revision,
                    now,
                ),
            )
            return key

    def finish_generation(self, request_id: str, state: str) -> None:
        with self.store.connection() as conn:
            conn.execute(
                "UPDATE generation_requests SET state=?,finished_us=? WHERE id=?",
                (state, time.time_ns() // 1000, request_id),
            )

    def available_requests(self) -> int:
        policy = GenerationBudget.load(self.store)
        with self.store.connection() as conn:
            used = conn.execute(
                "SELECT COUNT(*) FROM generation_requests WHERE created_us>=?",
                (time.time_ns() // 1000 - 86_400_000_000,),
            ).fetchone()[0]
        return max(0, min(policy.per_run, policy.per_day - used))

    def report(self, campaign_id: str) -> dict[str, object]:
        with self.store.connection() as conn:
            attempts = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT a.outcome,COUNT(*) FROM attempts a JOIN messages m ON m.id=a.message_id WHERE m.campaign_id=? GROUP BY a.outcome",
                    (campaign_id,),
                )
            }
            feedback = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT f.kind,COUNT(*) FROM feedback_events f JOIN messages m ON m.id=f.message_id WHERE m.campaign_id=? GROUP BY f.kind",
                    (campaign_id,),
                )
            }
            return {
                "transport_attempts": attempts,
                "operator_reviewed_feedback": feedback,
                "delivery_status": "Not established by SMTP acceptance or imported reply files",
                "generation_requests": conn.execute(
                    "SELECT COUNT(*) FROM generation_requests WHERE campaign_id=?", (campaign_id,)
                ).fetchone()[0],
                "frozen_runs": [
                    dict(row)
                    for row in conn.execute(
                        "SELECT id,created_us,finished_us,state,summary FROM frozen_runs WHERE campaign_id=? ORDER BY created_us DESC LIMIT 100",
                        (campaign_id,),
                    )
                ],
            }

    def restore_revision(self, message_id: str, revision_id: str, expected_revision: int) -> None:
        with self.store.connection() as conn:
            row = conn.execute(
                "SELECT subject,body,instructions FROM message_revisions WHERE id=? AND message_id=?",
                (revision_id, message_id),
            ).fetchone()
        if row is None:
            raise ValidationError("The saved revision does not belong to this message.")
        self.store.save_draft(
            message_id, row[0], row[1], expected_revision, instructions=row[2], origin="restored"
        )
