import json
import smtplib
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from google.genai import types

from cold_mailer.domain.models import Outcome, ValidationError
from cold_mailer.infrastructure.ai import AIGenerator
from cold_mailer.infrastructure.legacy import read_legacy_accounts
from cold_mailer.infrastructure.smtp import SMTPTransport
from cold_mailer.settings import Settings
from tests.conftest import Rig

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("mode", ["starttls", "tls"])
def test_transport_verifies_tls_and_quit_failure_does_not_undo_acceptance(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from dataclasses import replace

    message = rig.message()
    socket = MagicMock()
    socket.send_message.return_value = {}
    socket.quit.side_effect = OSError("fixture cleanup failure")
    constructor = MagicMock(return_value=socket)
    monkeypatch.setattr(smtplib, "SMTP_SSL" if mode == "tls" else "SMTP", constructor)
    result = SMTPTransport(Settings(rig.store.path.parent, network=True)).send(
        replace(rig.sender, tls=mode), "test-password", message
    )
    assert result.outcome == Outcome.ACCEPTED
    socket.close.assert_called_once()
    if mode == "starttls":
        context = socket.starttls.call_args.kwargs["context"]
        assert context.check_hostname
    mail = socket.send_message.call_args.args[0]
    assert mail["Message-ID"] == message.message_id
    assert socket.send_message.call_args.kwargs["to_addrs"] == [message.recipient]


@pytest.mark.parametrize(
    "error,outcome",
    [
        (smtplib.SMTPAuthenticationError(535, b"secret fixture"), Outcome.FAILED),
        (smtplib.SMTPDataError(451, b"temporary"), Outcome.RETRYABLE),
        (smtplib.SMTPDataError(550, b"refused"), Outcome.FAILED),
        (OSError("lost response"), Outcome.UNCERTAIN),
        (smtplib.SMTPRecipientsRefused({"a@example.com": (450, b"temporary")}), Outcome.RETRYABLE),
    ],
)
def test_protocol_error_classification(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, error: Exception, outcome: Outcome
) -> None:
    socket = MagicMock()
    socket.send_message.side_effect = error
    monkeypatch.setattr(smtplib, "SMTP", MagicMock(return_value=socket))
    result = SMTPTransport(Settings(rig.store.path.parent, network=True)).send(
        rig.sender, "pw", rig.message()
    )
    assert result.outcome == outcome
    assert "secret" not in result.code


def test_connect_failure_is_retryable_and_offline_never_opens_socket(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValidationError):
        SMTPTransport(Settings(rig.store.path.parent)).preflight()
    SMTPTransport(Settings(rig.store.path.parent, network=True)).preflight()
    constructor = MagicMock(side_effect=OSError("not connected"))
    monkeypatch.setattr(smtplib, "SMTP", constructor)
    message = rig.message()
    with pytest.raises(ValidationError):
        SMTPTransport(Settings(rig.store.path.parent)).send(rig.sender, "pw", message)
    constructor.assert_not_called()
    assert (
        SMTPTransport(Settings(rig.store.path.parent, network=True))
        .send(rig.sender, "pw", message)
        .outcome
        == Outcome.RETRYABLE
    )


def test_ai_explicit_model_bounded_call_and_redacted_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from google import genai

    client = MagicMock()
    client.__enter__.return_value = client
    client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps({"subject": "Subject", "body": "Body"})
    )
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(genai, "Client", constructor)
    settings = Settings(tmp_path, model="selected-model", api_key="synthetic-key", network=True)
    assert AIGenerator(settings).generate(
        "Facts only",
        {"first_name": "Alex", "email": "private@example.com", "notes": "do not transmit"},
    ) == ("Subject", "Body")
    request = client.models.generate_content.call_args
    assert request.kwargs["model"] == "selected-model"
    assert "private@example.com" not in request.kwargs["contents"]
    assert "do not transmit" not in request.kwargs["contents"]
    assert isinstance(constructor.call_args.kwargs["http_options"], types.HttpOptions)
    client.models.generate_content.side_effect = RuntimeError("synthetic-key must never leak")
    with pytest.raises(ValidationError) as error:
        AIGenerator(settings).generate("Facts", {})
    assert "synthetic-key" not in str(error.value)


def test_ai_missing_configuration_and_bad_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValidationError):
        AIGenerator(Settings(tmp_path, network=True)).generate("brief", {})
    from google import genai

    client = MagicMock()
    client.__enter__.return_value = client
    client.models.generate_content.return_value = SimpleNamespace(text='{"body": 123}')
    monkeypatch.setattr(genai, "Client", MagicMock(return_value=client))
    with pytest.raises(ValidationError):
        AIGenerator(Settings(tmp_path, model="model", api_key="fixture", network=True)).generate(
            "brief", {}
        )


def test_explicit_legacy_import_never_changes_database_or_key(tmp_path: Path) -> None:
    path, key = tmp_path / "old.db", tmp_path / "old.key"
    key.write_bytes(Fernet.generate_key())
    encrypted = Fernet(key.read_bytes()).encrypt(b"synthetic-password").decode()
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE sender_accounts(id,email,smtp_server,port,username,encrypted_password)"
        )
        connection.execute(
            "INSERT INTO sender_accounts VALUES(1,'a@example.com','smtp.example.com',587,'a',?)",
            (encrypted,),
        )
    before = path.read_bytes(), key.read_bytes()
    accounts = read_legacy_accounts(path, key)
    assert accounts[0].password == "synthetic-password"
    assert "synthetic-password" not in repr(accounts)
    assert before == (path.read_bytes(), key.read_bytes())
    key.write_bytes(Fernet.generate_key())
    with pytest.raises(ValidationError):
        read_legacy_accounts(path, key)
    with pytest.raises(ValidationError):
        read_legacy_accounts(path, tmp_path / "missing.key")
