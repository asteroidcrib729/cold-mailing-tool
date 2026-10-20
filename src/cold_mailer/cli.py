"""Offline-first CLI sharing the desktop application's persistent services."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, replace
from datetime import datetime
from getpass import getpass
from pathlib import Path
from threading import Event

from cold_mailer.bootstrap import Application
from cold_mailer.domain.models import Sender, ValidationError, identifier
from cold_mailer.infrastructure.ai import AIGenerator
from cold_mailer.infrastructure.backup import encrypted_backup, restore_encrypted
from cold_mailer.infrastructure.contacts import load_contacts
from cold_mailer.infrastructure.doctor import diagnostics
from cold_mailer.infrastructure.history import export_history
from cold_mailer.infrastructure.storage import Store
from cold_mailer.settings import VERSION, Settings


def history_instant(value: str) -> float:
    try:
        instant = datetime.fromisoformat(value)
        if instant.tzinfo is None:
            raise ValueError
        return instant.timestamp()
    except ValueError, OverflowError:
        raise argparse.ArgumentTypeError(
            "Use an ISO-8601 timestamp with UTC Z or an offset."
        ) from None


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Local campaign editor. Network is disabled unless --live is supplied."
    )
    root.add_argument("--version", action="version", version=VERSION)
    root.add_argument("--data-dir", type=Path)
    root.add_argument(
        "--development", action="store_true", help="Explicitly read .env from the current directory"
    )
    root.add_argument(
        "--live", action="store_true", help="Allow explicitly requested provider calls"
    )
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("diagnostics")
    commands.add_parser("doctor")
    history = commands.add_parser("history")
    history.add_argument("--query", default="")
    history.add_argument(
        "--outcome",
        choices=["", "accepted", "retryable", "failed", "uncertain", "sending"],
        default="",
    )
    history.add_argument("--limit", type=int, default=100)
    history.add_argument("--offset", type=int, default=0)
    history.add_argument("--export", type=Path)
    history.add_argument(
        "--since", type=history_instant, help="Inclusive ISO-8601 instant with offset"
    )
    history.add_argument(
        "--until", type=history_instant, help="Exclusive ISO-8601 instant with offset"
    )
    commands.add_parser("campaigns")
    create = commands.add_parser("create")
    create.add_argument("name")
    sender = commands.add_parser("add-sender")
    for field in ("email", "host", "username"):
        sender.add_argument("--" + field, required=True)
    sender.add_argument("--port", type=int, default=587)
    sender.add_argument("--tls", choices=["starttls", "tls"], default="starttls")
    sender.add_argument("--daily-limit", type=int, default=50)
    sender.add_argument("--interval", type=float, default=30)
    commands.add_parser("senders")
    contacts = commands.add_parser("import")
    contacts.add_argument("campaign")
    contacts.add_argument("sender")
    contacts.add_argument("file", type=Path)
    contacts.add_argument(
        "--rotate-senders",
        action="store_true",
        help="Assign contacts across all configured senders before review",
    )
    for name in ("messages", "dry-run", "run", "generate"):
        command = commands.add_parser(name)
        command.add_argument("campaign")
    edit = commands.add_parser("edit")
    edit.add_argument("message")
    edit.add_argument("--subject", required=True)
    edit.add_argument("--body-file", type=Path, required=True)
    approve = commands.add_parser("approve")
    approve.add_argument("message")
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("message")
    reconcile.add_argument("--outcome", choices=["accepted", "not-sent"], required=True)
    suppress = commands.add_parser("suppress")
    suppress.add_argument("email")
    backup = commands.add_parser("backup")
    backup.add_argument("destination", type=Path)
    backup.add_argument("--encrypted", action="store_true")
    restore = commands.add_parser("restore")
    restore.add_argument("source", type=Path)
    restore.add_argument("destination", type=Path)
    restore.add_argument("--encrypted", action="store_true")
    return root


def execute(args: argparse.Namespace, application: Application) -> tuple[object, int]:
    store = application.store
    match args.command:
        case "doctor":
            return diagnostics(), 0
        case "history":
            if args.export:
                return {
                    "exported": export_history(
                        store,
                        args.export,
                        args.query,
                        args.outcome,
                        since=args.since,
                        until=args.until,
                    )
                }, 0
            return store.history(
                args.query,
                args.outcome,
                limit=args.limit,
                offset=args.offset,
                since=args.since,
                until=args.until,
            ), 0
        case "diagnostics":
            return {
                "version": VERSION,
                "profile": str(application.settings.data_dir),
                "network_enabled": application.settings.network,
                "recovered_uncertain": application.recovered,
                "campaigns": len(store.campaigns()),
                "senders": len(store.senders()),
                "model_configured": bool(application.settings.model),
            }, 0
        case "create":
            return {"campaign": store.create_campaign(args.name)}, 0
        case "campaigns":
            return store.campaigns(), 0
        case "senders":
            return [asdict(sender) for sender in store.senders()], 0
        case "add-sender":
            sender = Sender(
                identifier(),
                args.email,
                args.host,
                args.port,
                args.username,
                args.tls,
                args.daily_limit,
                args.interval,
            )
            sender.validate()
            application.credentials.set(
                sender.id, getpass("SMTP password (stored in OS keyring): ")
            )
            store.save_sender(sender)
            return {"sender": sender.id}, 0
        case "import":
            report = load_contacts(args.file, store.suppressed())
            count = store.add_contacts(
                args.campaign,
                args.sender,
                report.contacts,
                rotate=[sender.id for sender in store.senders()] if args.rotate_senders else None,
            )
            return {
                "added": count,
                "existing": len(report.contacts) - count,
                "duplicates": report.duplicates,
                "suppressed": report.suppressed,
                "issues": [asdict(issue) for issue in report.issues],
            }, 0
        case "messages":
            return [
                {
                    "id": msg.id,
                    "recipient": msg.recipient,
                    "status": msg.status.value,
                    "revision": msg.revision,
                }
                for msg in store.messages(args.campaign)
            ], 0
        case "edit":
            msg = store.message(args.message)
            store.edit(
                msg.id, args.subject, args.body_file.read_text(encoding="utf-8"), msg.revision
            )
            return {"saved": msg.id, "approval_invalidated": True}, 0
        case "approve":
            msg = store.message(args.message)
            store.approve(msg.id, msg.revision)
            return {"approved": msg.id}, 0
        case "dry-run":
            return application.service.dry_run(args.campaign), 0
        case "generate" | "run":
            application.settings.require_network()
            stop = Event()
            if args.command == "generate":
                summary = application.service.generate(
                    args.campaign,
                    AIGenerator(
                        replace(
                            application.settings,
                            api_key=application.credentials.get("google-api-key")
                            or application.settings.api_key,
                        )
                    ),
                    stop,
                )
            else:
                summary = application.service.run(args.campaign, stop)
            return asdict(summary), 5 if summary.uncertain else (
                3 if summary.failed or summary.retryable else 0
            )
        case "reconcile":
            store.reconcile(args.message, args.outcome == "accepted")
            return {"reconciled": args.message}, 0
        case "suppress":
            store.suppress(args.email)
            return {"suppressed": True}, 0
        case "backup":
            if args.encrypted:
                encrypted_backup(
                    store, args.destination, getpass("Backup passphrase (12+ characters): ")
                )
            else:
                store.backup(args.destination)
            return {"backup": str(args.destination)}, 0
        case "restore":
            if args.encrypted:
                restore_encrypted(args.source, args.destination, getpass("Backup passphrase: "))
            else:
                Store.restore(args.source, args.destination)
            return {
                "restored": str(args.destination),
                "pending_messages_held_uncertain": True,
                "credentials_require_existing_OS_profile_or_reentry": True,
            }, 0
    raise ValidationError("Unsupported command.")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            print(json.dumps(diagnostics(), indent=2))
            return 0
        settings = Settings.load(args.data_dir, development=args.development, network=args.live)
        with Application(settings) as application:
            result, code = execute(args, application)
        print(json.dumps(result, indent=2))
        return code
    except ValidationError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except OSError, sqlite3.Error:
        print(
            json.dumps(
                {"error": "Storage or file access failed. Check permissions and profile integrity."}
            ),
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print(
            json.dumps({"error": "Interrupted. In-flight attempts require recovery before retry."}),
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
