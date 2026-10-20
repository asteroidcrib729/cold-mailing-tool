"""Sequential, transactional upgrades; legacy facts are never reconstructed."""

import sqlite3

VERSION = 3

UPGRADE_2 = """
ALTER TABLE messages ADD COLUMN created_us INTEGER;
ALTER TABLE messages ADD COLUMN updated_us INTEGER;
ALTER TABLE messages ADD COLUMN instructions TEXT NOT NULL DEFAULT '';
ALTER TABLE attempts ADD COLUMN sender_email TEXT;
ALTER TABLE attempts ADD COLUMN recipient TEXT;
ALTER TABLE attempts ADD COLUMN subject TEXT;
ALTER TABLE attempts ADD COLUMN body TEXT;
ALTER TABLE attempts ADD COLUMN revision INTEGER;
ALTER TABLE attempts ADD COLUMN content_hash TEXT;
ALTER TABLE attempts ADD COLUMN snapshot_known INTEGER NOT NULL DEFAULT 0;
CREATE TABLE message_revisions(
 id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id),
 revision INTEGER NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
 instructions TEXT NOT NULL, sender_email TEXT NOT NULL, recipient TEXT NOT NULL,
 saved_us INTEGER NOT NULL, origin TEXT NOT NULL, content_hash TEXT NOT NULL);
CREATE INDEX revision_message ON message_revisions(message_id, saved_us);
CREATE INDEX attempt_history ON attempts(started DESC, id);
CREATE TABLE schedule_state(sender_id TEXT PRIMARY KEY REFERENCES senders(id),
 attempt_id TEXT NOT NULL, finished REAL NOT NULL, base REAL NOT NULL,
 jitter REAL NOT NULL, due REAL NOT NULL);
CREATE TABLE blueprints(id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL,
 prompt TEXT NOT NULL, wrapper TEXT NOT NULL, created_us INTEGER NOT NULL,
 UNIQUE(name, version));
CREATE TRIGGER immutable_attempt_snapshot BEFORE UPDATE OF sender_email,recipient,subject,
 body,revision,content_hash,snapshot_known ON attempts BEGIN
 SELECT RAISE(ABORT, 'Attempt snapshots are immutable'); END;
CREATE TRIGGER immutable_revision_update BEFORE UPDATE ON message_revisions BEGIN
 SELECT RAISE(ABORT, 'Saved revisions are immutable'); END;
CREATE TRIGGER immutable_revision_delete BEFORE DELETE ON message_revisions BEGIN
 SELECT RAISE(ABORT, 'Saved revisions are immutable'); END;
"""


UPGRADE_3 = """
CREATE TABLE import_batches(id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id),
 source_label TEXT NOT NULL, source_sha256 TEXT NOT NULL, permission_note TEXT NOT NULL,
 reviewed INTEGER NOT NULL, created_us INTEGER NOT NULL, added INTEGER NOT NULL DEFAULT 0);
CREATE TABLE contact_sources(message_id TEXT NOT NULL REFERENCES messages(id), batch_id TEXT NOT NULL REFERENCES import_batches(id), PRIMARY KEY(message_id,batch_id));
CREATE TABLE frozen_runs(id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id),
 created_us INTEGER NOT NULL, finished_us INTEGER, state TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '{}');
CREATE TABLE run_messages(run_id TEXT NOT NULL REFERENCES frozen_runs(id), message_id TEXT NOT NULL REFERENCES messages(id),
 revision INTEGER NOT NULL, approval TEXT, PRIMARY KEY(run_id,message_id));
CREATE TRIGGER immutable_run_membership BEFORE UPDATE ON run_messages BEGIN SELECT RAISE(ABORT,'Run selections are immutable'); END;
CREATE TRIGGER immutable_run_membership_delete BEFORE DELETE ON run_messages BEGIN SELECT RAISE(ABORT,'Run selections are immutable'); END;
ALTER TABLE attempts ADD COLUMN run_id TEXT REFERENCES frozen_runs(id);
CREATE TABLE generation_requests(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, campaign_id TEXT NOT NULL REFERENCES campaigns(id),
 message_id TEXT NOT NULL REFERENCES messages(id), model TEXT NOT NULL, brief_hash TEXT NOT NULL,
 revision INTEGER NOT NULL, state TEXT NOT NULL, created_us INTEGER NOT NULL, finished_us INTEGER);
CREATE INDEX generation_daily ON generation_requests(created_us);
CREATE TABLE feedback_events(id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id), kind TEXT NOT NULL,
 source_sha256 TEXT NOT NULL UNIQUE, received_utc TEXT, recorded_us INTEGER NOT NULL, text TEXT NOT NULL);
CREATE TABLE audit_events(id TEXT PRIMARY KEY, message_id TEXT REFERENCES messages(id), kind TEXT NOT NULL,
 recorded_us INTEGER NOT NULL, detail TEXT NOT NULL);
CREATE INDEX history_outcome_time ON attempts(outcome,started DESC,id);
CREATE INDEX attempts_message ON attempts(message_id);
"""


def migrate(connection: sqlite3.Connection, version: int) -> None:
    if version == 1:
        connection.executescript("BEGIN IMMEDIATE;" + UPGRADE_2 + "PRAGMA user_version=2; COMMIT;")
        version = 2
    if version == 2:
        connection.executescript("BEGIN IMMEDIATE;" + UPGRADE_3 + "PRAGMA user_version=3; COMMIT;")
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise sqlite3.DatabaseError("Profile integrity check failed")
