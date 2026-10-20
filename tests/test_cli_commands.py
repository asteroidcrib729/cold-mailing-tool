from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cold_mailer import cli as main_headless
from cold_mailer.bootstrap import Application
from cold_mailer.cli import execute, main, parser
from cold_mailer.domain.models import Sender, Status, ValidationError
from cold_mailer.infrastructure.storage import Store
from cold_mailer.settings import Settings
from tests.conftest import Rig

pytestmark = pytest.mark.integration


def test_cli_shared_services_complete_workflow(
    rig: Rig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Application(Settings(rig.store.path.parent, network=True, model="fixture-model")) as app:
        app.credentials, app.service = rig.credentials, rig.service
        rig.service.clock = lambda: 100

        def command(*arguments: str):
            return execute(parser().parse_args(list(arguments)), app)

        assert command("campaigns")[1] == command("senders")[1] == 0
        connected = Sender(
            "other",
            "other@gmail.com",
            "gmail.googleapis.com",
            443,
            "other@gmail.com",
            "tls",
            provider="google",
            subject="person",
        )
        connect_mock = MagicMock(return_value=connected)
        monkeypatch.setattr(app.accounts, "connect", connect_mock)
        added, code = command("--live", "connect-account", "google")
        assert code == 0 and added
        connect_mock.assert_called_once()
        monkeypatch.setattr(app.accounts, "disconnect", MagicMock())
        assert command("disconnect-account", connected.id)[1] == 0
        contacts = tmp_path / "cli.csv"
        contacts.write_text("email,first_name\na@example.com,Alex\nb@example.com,Bee\n")
        imported, _ = command("import", rig.campaign, rig.sender.id, str(contacts))
        assert isinstance(imported, dict)
        assert imported["added"] == 2
        ai = MagicMock()
        ai.generate.return_value = ("Generated subject", "Generated body")
        monkeypatch.setattr(main_headless, "AIGenerator", MagicMock(return_value=ai))
        assert command("generate", rig.campaign)[1] == 0
        messages, _ = command("messages", rig.campaign)
        assert isinstance(messages, list)
        assert len(messages) == 2
        first, second = rig.store.messages(rig.campaign)
        body = tmp_path / "body.txt"
        body.write_text("Reviewed body")
        command("edit", first.id, "--subject", "Reviewed subject", "--body-file", str(body))
        command("approve", first.id)
        assert command("dry-run", rig.campaign)[0] == {"approved": 1, "draft": 1}
        assert command("run", rig.campaign)[1] == 0
        assert rig.store.message(first.id).status == Status.ACCEPTED
        command("approve", second.id)
        assert rig.store.claim(second.id, 100)
        rig.store.recover()
        command("reconcile", second.id, "--outcome", "not-sent")
        assert rig.store.message(second.id).status == Status.DRAFT
        command("suppress", second.recipient)
        backup = tmp_path / "backup.sqlite3"
        assert command("backup", str(backup))[1] == 0
        restored = tmp_path / "restored" / "campaigns.sqlite3"
        assert command("restore", str(backup), str(restored))[1] == 0
        assert Store(restored).message(first.id).status == Status.ACCEPTED


def test_restore_holds_old_queued_messages_and_preserves_original(rig: Rig, tmp_path: Path) -> None:
    message = rig.message()
    source = tmp_path / "backup.sqlite3"
    rig.store.backup(source)
    before = source.read_bytes()
    target = tmp_path / "restored.sqlite3"
    Store.restore(source, target)
    assert source.read_bytes() == before
    assert Store(target).message(message.id).status == Status.UNCERTAIN
    with pytest.raises(ValidationError):
        Store.restore(source, target)


def test_cli_interrupt_and_storage_failure_are_useful(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    options = ["--data-dir", str(tmp_path / "profile")]
    monkeypatch.setattr(main_headless, "execute", MagicMock(side_effect=KeyboardInterrupt()))
    assert main([*options, "diagnostics"]) == 130
    assert "Interrupted" in capsys.readouterr().err
    monkeypatch.setattr(main_headless, "execute", MagicMock(side_effect=OSError("private detail")))
    assert main([*options, "diagnostics"]) == 1
    assert "private detail" not in capsys.readouterr().err
