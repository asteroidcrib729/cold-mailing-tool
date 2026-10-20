import sqlite3
from contextlib import closing
from dataclasses import replace
from threading import Event
from unittest.mock import MagicMock

import httpx
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from cold_mailer.application.campaigns import CampaignService
from cold_mailer.bootstrap import Application
from cold_mailer.domain.models import Sender, Status, ValidationError
from cold_mailer.infrastructure import oauth_mail
from cold_mailer.infrastructure.credentials import MemoryCredentials
from cold_mailer.infrastructure.migrations import UPGRADE_2, UPGRADE_3
from cold_mailer.infrastructure.oauth_accounts import OAuthAccounts
from cold_mailer.infrastructure.oauth_mail import OAuthMailTransport, retry_delay
from cold_mailer.infrastructure.storage import SCHEMA, Store
from cold_mailer.settings import Settings
from cold_mailer.ui.window import Window
from tests.conftest import Rig


def authorized_sender(sender_id="sender"):
    return Sender(
        sender_id,
        "person@gmail.com",
        "gmail.googleapis.com",
        443,
        "person@gmail.com",
        "tls",
        interval=0,
        provider="google",
        subject="personal-subject",
    )


@pytest.mark.parametrize(
    "status,expected",
    [
        (200, Status.ACCEPTED),
        (401, Status.FAILED),
        (429, Status.RETRYABLE),
        (504, Status.UNCERTAIN),
    ],
)
def test_oauth_engine_journals_approved_content_and_stops_on_throttle_or_uncertainty(
    rig: Rig, monkeypatch, status, expected
):
    rig.store.save_sender(authorized_sender())
    first = rig.message()
    second = rig.message("other@example.com")
    settings = Settings(rig.store.path.parent, network=True)
    accounts = OAuthAccounts(settings, rig.store, rig.credentials)
    monkeypatch.setattr(accounts, "access_token", lambda _: "synthetic-token")
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = httpx.Response(
        status, json={"id": "synthetic-provider-id"}, headers={"Retry-After": "360"}
    )
    monkeypatch.setattr(oauth_mail.httpx, "Client", lambda **_: client)
    clock = [100.0]

    class Stop(Event):
        def wait(self, timeout=None):
            clock[0] += timeout or 0
            return False

    service = CampaignService(
        rig.store, rig.credentials, OAuthMailTransport(settings, accounts), lambda: clock[0]
    )
    summary = service.run(rig.campaign, Stop())
    assert rig.store.message(first.id).status == expected
    assert len(rig.store.history()) == (2 if status == 200 else 1)
    assert rig.store.history()[0]["subject"] == first.subject
    assert client.post.call_count == (2 if status == 200 else 1)
    if status == 429:
        assert rig.store.message(second.id).status == Status.APPROVED
        assert rig.store.wait_seconds(rig.sender.id, 100) >= 360
        assert summary.retryable == 1
    if status == 504:
        assert summary.uncertain == 1
        before = client.post.call_count
        rig.store.suppress(second.recipient)
        service.run(rig.campaign, Stop())
        assert client.post.call_count == before


def test_refresh_happens_after_pacing_wait_before_attempt_admission(rig: Rig, monkeypatch):
    rig.store.save_sender(authorized_sender())
    rig.message()
    settings = Settings(rig.store.path.parent, network=True)
    accounts = OAuthAccounts(settings, rig.store, rig.credentials)
    clock = [100.0]
    observed = []

    def token(_):
        observed.append(clock[0])
        assert not rig.store.history()
        return "fresh-token"

    monkeypatch.setattr(accounts, "access_token", token)
    monkeypatch.setattr(rig.store, "wait_seconds", lambda *a, **kw: 600)
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = httpx.Response(200, json={"id": "provider-id"})
    monkeypatch.setattr(oauth_mail.httpx, "Client", lambda **_: client)

    class Stop(Event):
        def wait(self, timeout=None):
            clock[0] += timeout or 0
            return False

    CampaignService(
        rig.store, rig.credentials, OAuthMailTransport(settings, accounts), lambda: clock[0]
    ).run(rig.campaign, Stop())
    assert observed == [700]


@pytest.mark.parametrize(
    "header,expected",
    [
        ("360", 360),
        ("-10", 60),
        ("bad", 60),
        ("nan", 60),
        ("inf", 60),
        ("", 60),
        ("Thu, 01 Jan 1970 00:00:00 GMT", 60),
    ],
)
def test_retry_after_parsing_is_finite_and_conservative(header, expected):
    assert retry_delay(header) == expected


def test_schema_v3_upgrade_holds_old_approvals_but_preserves_history(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(SCHEMA + UPGRADE_2 + UPGRADE_3 + "PRAGMA user_version=3;")
        conn.execute(
            "INSERT INTO senders VALUES ('s','person@gmail.com','smtp.gmail.com',587,'person@gmail.com','starttls',50,30)"
        )
        conn.execute("INSERT INTO campaigns VALUES ('c','Existing','','{{ AI_GENERATED_BODY }}')")
        for status in ("approved", "retryable", "accepted", "uncertain"):
            conn.execute(
                "INSERT INTO messages(id,campaign_id,sender_id,recipient,contact,message_id,status,approval) VALUES (?,'c','s',?,'{}',?,?,?)",
                (status, status + "@example.com", status, status, "old-fingerprint"),
            )
        conn.commit()
    store = Store(path)
    assert store.sender("s").provider == "" and store.sender("s").subject == ""
    for key in ("approved", "retryable"):
        assert store.message(key).status == Status.DRAFT and store.message(key).approval is None
    for key in ("accepted", "uncertain"):
        assert (
            store.message(key).status.value == key
            and store.message(key).approval == "old-fingerprint"
        )
    assert len(list(tmp_path.glob("*.bak"))) == 1
    with store.connection() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 4


@pytest.mark.ui
def test_sender_page_has_only_explicit_provider_login_and_read_only_identity(
    qtbot, tmp_path, monkeypatch
):
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda p, t, text: messages.append(text))
    with Application(Settings(tmp_path / "profile")) as app:
        app.credentials = MemoryCredentials()
        window = Window(app)
        qtbot.addWidget(window)
        window.show()
        window.tabs.setCurrentIndex(1)
        assert window.sender_email.isReadOnly()
        assert not hasattr(window, "sender_fields") and not hasattr(window, "port")
        window.save_sender()
        assert "Sign in" in messages[-1]
        window.disconnect_account()
        assert "Select" in messages[-1]
        qtbot.mouseClick(window.google_sign_in, Qt.MouseButton.LeftButton)
        assert "live mode" in messages[-1]
        window.live.setChecked(True)
        calls = []

        def connect(self, provider, stop, sender_id=None):
            calls.append(provider)
            value = replace(
                authorized_sender("connected"),
                email="person@outlook.com",
                username="person@outlook.com",
                provider="microsoft",
            )
            self.store.save_sender(value)
            return value

        monkeypatch.setattr(OAuthAccounts, "connect", connect)
        qtbot.mouseClick(window.microsoft_sign_in, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        assert calls == ["microsoft"] and window.sender_email.text() == "person@outlook.com"
        window.limit.setValue(12)
        window.save_sender()
        assert app.store.sender("connected").daily_limit == 12
        window.disconnect_account()
        assert "Sign-in required" in window.sender_status.text()
        window.close()


def test_disconnect_cannot_mutate_while_send_lock_is_held(rig: Rig):
    from filelock import FileLock

    accounts = OAuthAccounts(Settings(rig.store.path.parent), rig.store, rig.credentials)
    message = rig.message()
    with (
        FileLock(str(rig.store.path) + ".send.lock", timeout=0),
        pytest.raises(ValidationError, match="disconnect"),
    ):
        accounts.disconnect(rig.sender.id)
    assert rig.store.message(message.id).approval == message.approval
