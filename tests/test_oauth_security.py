import base64
import json
from dataclasses import replace
from http.client import HTTPConnection
from threading import Event, Thread
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest

from cold_mailer.application.campaigns import CampaignService
from cold_mailer.domain.models import Outcome, Sender, Status, ValidationError
from cold_mailer.infrastructure import oauth_accounts as accounts_module
from cold_mailer.infrastructure import oauth_browser as browser
from cold_mailer.infrastructure import oauth_mail as mail_module
from cold_mailer.infrastructure.credentials import MemoryCredentials
from cold_mailer.infrastructure.oauth_accounts import (
    CONSUMER_AUTHORITY,
    CONSUMER_TENANT,
    GMAIL_SEND,
    OAuthAccounts,
)
from cold_mailer.infrastructure.oauth_mail import OAuthMailTransport
from cold_mailer.infrastructure.oauth_secrets import OAuthSecrets
from cold_mailer.settings import Settings
from tests.conftest import Rig


@pytest.fixture
def accounts(rig: Rig) -> OAuthAccounts:
    rig.store.save_preference("oauth.connected.oauth-person", "true")
    return OAuthAccounts(
        Settings(
            rig.store.path.parent,
            network=True,
            google_oauth_client_id="fixture.apps.googleusercontent.com",
            google_oauth_client_secret="synthetic-client-configuration",
            microsoft_oauth_client_id="00000000-0000-4000-8000-000000000001",
        ),
        rig.store,
        rig.credentials,
    )


def sender(provider="google") -> Sender:
    email = "person@gmail.com" if provider == "google" else "person@outlook.com"
    return Sender(
        "oauth-person",
        email,
        "provider.example.com",
        443,
        email,
        "tls",
        provider=provider,
        subject="personal-subject",
    )


def session(accounts: OAuthAccounts, provider="google") -> dict:
    value = sender(provider)
    return {
        "provider": provider,
        "subject": value.subject,
        "email": value.email,
        "client_id": accounts.settings.google_oauth_client_id
        if provider == "google"
        else accounts.settings.microsoft_oauth_client_id,
        "credentials": "{}",
        "cache": "{}",
        "account_id": "personal-home",
    }


def fake_browser(authorize, stop, **kwargs):
    url = authorize("http://127.0.0.1:12345/oauth/callback", "synthetic-state")
    assert url.startswith("https://")
    return "http://127.0.0.1:12345/oauth/callback", {
        "code": "synthetic-code",
        "state": "synthetic-state",
    }


def test_os_token_chunks_replace_disconnect_and_do_not_touch_database(rig: Rig):
    vault = OAuthSecrets(rig.credentials)
    original = rig.store.path.read_bytes()
    value = {"cache": "synthetic-cache-" * 700}
    vault.save("person", value)
    assert vault.load("person") == value
    assert max(map(len, rig.credentials._values.values())) <= 1000
    previous = {key for key in rig.credentials._values if key.startswith("oauth:")}
    vault.save("person", {"cache": "replacement"})
    assert vault.load("person") == {"cache": "replacement"}
    assert not (previous - {"oauth:person"}) & set(rig.credentials._values)
    vault.delete("person")
    assert "oauth:person" not in rig.credentials._values
    assert rig.store.path.read_bytes() == original
    with pytest.raises(ValidationError, match="Sign in"):
        vault.load("person")


@pytest.mark.parametrize(
    "value",
    [
        "bad-json",
        "[]",
        '{"generation":"invalid","count":1}',
        '{"generation":"' + "a" * 32 + '","count":0}',
        '{"generation":"' + "a" * 32 + '","count":true}',
    ],
)
def test_damaged_manifest_fails_closed_and_can_be_disconnected(value):
    credentials = MemoryCredentials()
    credentials.set("oauth:s", value)
    vault = OAuthSecrets(credentials)
    with pytest.raises(ValidationError, match="damaged"):
        vault.load("s")
    vault.delete("s")
    assert credentials.get("oauth:s") is None


@pytest.mark.parametrize("chunk", [None, "x" * 1001, "not-json", "[]"])
def test_partial_or_invalid_cache_fails_closed(chunk):
    credentials = MemoryCredentials()
    credentials.set("oauth:s", json.dumps({"generation": "a" * 32, "count": 1}))
    if chunk is not None:
        credentials.set("oauth:s:" + "a" * 32 + ":0", chunk)
    with pytest.raises(ValidationError, match="incomplete"):
        OAuthSecrets(credentials).load("s")


def test_interrupted_secure_write_keeps_old_complete_cache(monkeypatch):
    credentials = MemoryCredentials()
    vault = OAuthSecrets(credentials)
    vault.save("s", {"old": "complete"})
    original_set = credentials.set

    def fail_publish(key, value):
        if key == "oauth:s":
            raise ValidationError("OS vault unavailable")
        original_set(key, value)

    monkeypatch.setattr(credentials, "set", fail_publish)
    with pytest.raises(ValidationError):
        vault.save("s", {"new": "not published"})
    assert vault.load("s") == {"old": "complete"}
    with pytest.raises(ValidationError, match="limit"):
        vault.save("s", {"large": "x" * 256001})


@pytest.mark.parametrize(
    "target",
    [
        "/wrong?state=expected&code=value",
        "/oauth/callback?state=wrong&code=value",
        "/oauth/callback?state=expected&code=one&code=two",
        "/oauth/callback?state=expected",
        "https://evil.example/oauth/callback?state=expected&code=value",
        "/oauth/callback?state=%C3%A9&code=value",
        "/oauth/callback?state=expected&code=" + "x" * 4097,
        "/oauth/callback?state=expected&code=value#fragment",
        "/oauth/callback?state=expected&code=" + "x" * 8193,
    ],
)
def test_callback_rejects_wrong_state_duplicates_and_wrong_paths(target):
    assert browser.callback_values(target, "/oauth/callback", "expected") is None


def test_callback_accepts_only_bound_success_or_decline():
    assert browser.callback_values(
        "/oauth/callback?state=expected&code=value", "/oauth/callback", "expected"
    ) == {"state": "expected", "code": "value"}
    assert browser.callback_values(
        "/oauth/callback?state=expected&error=access_denied&error_description=private",
        "/oauth/callback",
        "expected",
    ) == {"state": "expected", "error": "authorization_declined"}


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_real_loopback_browser_callback_checks_host_state_and_does_not_log_codes(
    socket_enabled, monkeypatch, capsys, host
):
    captured = {}
    replies = []
    threads = []

    def authorize(redirect, state):
        captured.update(redirect=redirect, state=state)
        return "https://accounts.google.com/o/oauth2/auth"

    def open_browser(url, new):
        def visit():
            parsed = urlsplit(captured["redirect"])
            conn = HTTPConnection("127.0.0.1", parsed.port, timeout=3)
            try:
                path = (
                    parsed.path
                    + "?"
                    + urlencode({"state": captured["state"], "code": "private-authorization-code"})
                )
                conn.request("GET", path, headers={"Host": "evil.example"})
                response = conn.getresponse()
                replies.append(response.status)
                response.read()
                conn.request("GET", path, headers={"Host": f"{host}:{parsed.port}"})
                response = conn.getresponse()
                replies.append(response.status)
                assert response.getheader("Cache-Control") == "no-store"
                response.read()
            finally:
                conn.close()

        thread = Thread(target=visit)
        thread.start()
        threads.append(thread)
        return True

    monkeypatch.setattr(browser.webbrowser, "open", open_browser)
    _, result = browser.authorize_in_browser(authorize, Event(), timeout=4, loopback_host=host)
    for thread in threads:
        thread.join(3)
    assert replies == [400, 200]
    assert result["code"] == "private-authorization-code"
    assert "private-authorization-code" not in str(capsys.readouterr())


@pytest.mark.parametrize(
    "url,opened",
    [
        ("http://accounts.google.com/auth", True),
        ("https://evil.example/auth", True),
        ("https://accounts.google.com/auth", False),
    ],
)
def test_browser_invalid_destination_or_launch_failure(socket_enabled, monkeypatch, url, opened):
    monkeypatch.setattr(browser.webbrowser, "open", lambda *a, **kw: opened)
    with pytest.raises(ValidationError, match="Could not open"):
        browser.authorize_in_browser(lambda *_: url, Event(), timeout=0)


def test_browser_timeout_initial_cancel_and_invalid_binding(socket_enabled, monkeypatch):
    stopped = Event()
    stopped.set()
    with pytest.raises(ValidationError, match="cancelled"):
        browser.authorize_in_browser(lambda *_: "unused", stopped)
    with pytest.raises(ValidationError, match="loopback"):
        browser.authorize_in_browser(lambda *_: "unused", Event(), loopback_host="0.0.0.0")
    monkeypatch.setattr(browser.webbrowser, "open", lambda *a, **kw: True)
    with pytest.raises(ValidationError, match="timed out"):
        browser.authorize_in_browser(
            lambda *_: "https://accounts.google.com/auth", Event(), timeout=0
        )


@pytest.mark.parametrize(
    "claims",
    [
        {"email": "person@gmail.com", "email_verified": False, "sub": "person"},
        {
            "email": "person@company.com",
            "email_verified": True,
            "sub": "person",
            "hd": "company.com",
        },
        {"email": "person@gmail.com", "email_verified": True, "sub": ""},
        {"email": "person@gmail.com", "email_verified": True, "sub": 123},
        {"email": "person@company.com", "email_verified": True, "sub": "person"},
    ],
)
def test_google_rejects_unverified_organizational_or_missing_identity(
    accounts, monkeypatch, claims
):
    verify = MagicMock(return_value=claims)
    monkeypatch.setattr(accounts_module.id_token, "verify_oauth2_token", verify)
    with pytest.raises(ValidationError):
        accounts._google_identity("synthetic-id-token")
    assert verify.call_args.args[2] == accounts.settings.google_oauth_client_id


def test_google_connect_uses_pkce_offline_grant_and_verified_send_only_scope(accounts, monkeypatch):
    flow = MagicMock()
    flow.authorization_url.return_value = ("https://accounts.google.com/auth", "synthetic-state")
    flow.credentials.id_token = "synthetic-id-token"
    flow.credentials.refresh_token = "synthetic-refresh"
    flow.credentials.to_json.return_value = "synthetic-credentials"
    monkeypatch.setattr(
        accounts_module.InstalledAppFlow, "from_client_config", MagicMock(return_value=flow)
    )
    monkeypatch.setattr(accounts_module, "authorize_in_browser", fake_browser)
    monkeypatch.setattr(
        accounts_module.id_token,
        "verify_oauth2_token",
        MagicMock(
            return_value={
                "email": "Person@gmail.com",
                "email_verified": True,
                "sub": "personal-subject",
            }
        ),
    )
    result = accounts._google_connect(Event())
    assert result["email"] == "person@gmail.com" and result["provider"] == "google"
    assert flow.authorization_url.call_args.kwargs["prompt"] == "select_account consent"
    assert flow.authorization_url.call_args.kwargs["access_type"] == "offline"
    flow.fetch_token.assert_called_once_with(code="synthetic-code", timeout=30)
    flow.credentials.has_scopes.assert_called_once_with([GMAIL_SEND])
    flow.credentials.has_scopes.return_value = False
    with pytest.raises(ValidationError, match="permission"):
        accounts._google_connect(Event())


def test_google_real_library_builds_s256_challenge_without_network(accounts, monkeypatch):
    def inspect_authorization(authorize, stop):
        url = authorize("http://127.0.0.1:1234/oauth/callback", "bound-state")
        query = parse_qs(urlsplit(url).query)
        assert query["code_challenge_method"] == ["S256"]
        assert query["state"] == ["bound-state"]
        assert GMAIL_SEND in query["scope"][0] and "gmail.readonly" not in query["scope"][0]
        raise ValidationError("test ended before token request")

    monkeypatch.setattr(accounts_module, "authorize_in_browser", inspect_authorization)
    with pytest.raises(ValidationError, match="test ended"):
        accounts._google_connect(Event())


@pytest.mark.parametrize("provider", ["google", "microsoft"])
def test_connection_reconnect_disconnect_and_binding(accounts, rig, monkeypatch, provider):
    grant = session(accounts, provider)
    monkeypatch.setattr(accounts, "_" + provider + "_connect", lambda _: grant.copy())
    connected = accounts.connect(provider, Event())
    assert connected.email == grant["email"] and connected.provider == provider
    assert "Signed in locally" in accounts.status(connected)
    reconnected = accounts.connect(provider, Event())
    assert reconnected.id == connected.id
    rig.store.add_contacts(rig.campaign, connected.id, [{"email": "recipient@example.com"}])
    message = rig.store.messages(rig.campaign)[0]
    rig.store.edit(message.id, "Reviewed", "Body", message.revision)
    rig.store.approve(message.id, rig.store.message(message.id).revision)
    accounts.disconnect(connected.id)
    assert "Sign-in required" in accounts.status(connected)
    assert rig.store.message(message.id).approval is None
    assert not rig.store.history()
    assert "synthetic" not in rig.store.path.read_bytes().decode("latin1")


def test_legacy_password_never_authorizes_production_transport(accounts, rig, monkeypatch):
    message = rig.message()
    client = MagicMock()
    monkeypatch.setattr(mail_module.httpx, "Client", client)
    service = CampaignService(
        rig.store, rig.credentials, OAuthMailTransport(accounts.settings, accounts)
    )
    with pytest.raises(ValidationError, match="retired"):
        service.run(rig.campaign, Event())
    client.assert_not_called()
    assert not rig.store.history() and rig.store.message(message.id).status == Status.APPROVED
    assert "Legacy SMTP" in accounts.status(rig.sender)


def test_reconnect_cannot_change_sender_identity_and_cancel_has_no_account(
    accounts, rig, monkeypatch
):
    grant = session(accounts)
    monkeypatch.setattr(accounts, "_google_connect", lambda _: grant.copy())
    with pytest.raises(ValidationError, match="same account"):
        accounts.connect("google", Event(), rig.sender.id)
    stopped = Event()
    stopped.set()
    with pytest.raises(ValidationError, match="cancelled"):
        accounts.connect("google", stopped)
    with pytest.raises(ValidationError, match="Choose"):
        accounts.connect("smtp", Event())
    assert len(rig.store.senders()) == 1


@pytest.mark.parametrize("field", ["provider", "subject", "email"])
def test_token_record_is_bound_to_sender(accounts, field):
    data = session(accounts)
    data[field] = "wrong"
    accounts.secrets.save(sender().id, data)
    with pytest.raises(ValidationError, match="identity"):
        accounts.access_token(sender())


def test_configuration_required_and_errors_never_expose_provider_response(accounts, monkeypatch):
    empty = OAuthAccounts(
        Settings(accounts.settings.data_dir, network=True),
        accounts.store,
        accounts.secrets.credentials,
    )
    for method in (empty._google_client, empty._microsoft_client):
        with pytest.raises(ValidationError, match="not configured"):
            method()
    monkeypatch.setattr(
        accounts, "_google_connect", MagicMock(side_effect=RuntimeError("secret response"))
    )
    with pytest.raises(ValidationError) as raised:
        accounts.connect("google", Event())
    assert "secret response" not in str(raised.value)


@pytest.mark.parametrize("valid", [True, False])
def test_google_token_refresh_is_bounded_and_saves_only_in_os_store(accounts, monkeypatch, valid):
    accounts.secrets.save(sender().id, session(accounts))
    credentials = MagicMock(valid=valid, token="synthetic-access-token")
    credentials.to_json.return_value = "{}"
    monkeypatch.setattr(
        accounts_module.Credentials,
        "from_authorized_user_info",
        MagicMock(return_value=credentials),
    )
    assert accounts.access_token(sender()) == "synthetic-access-token"
    assert credentials.refresh.call_count == (0 if valid else 1)
    credentials.has_scopes.return_value = False
    with pytest.raises(ValidationError, match="permission"):
        accounts.access_token(sender())


@pytest.mark.parametrize("failure", ["registration", "refresh", "empty"])
def test_refresh_failure_requires_new_explicit_sign_in(accounts, monkeypatch, failure):
    data = session(accounts)
    if failure == "registration":
        data["client_id"] = "wrong"
    accounts.secrets.save(sender().id, data)
    credentials = MagicMock(valid=False, token="" if failure == "empty" else "synthetic")
    credentials.to_json.return_value = "{}"
    if failure == "refresh":
        credentials.refresh.side_effect = RuntimeError("secret provider response")
    monkeypatch.setattr(
        accounts_module.Credentials,
        "from_authorized_user_info",
        MagicMock(return_value=credentials),
    )
    with pytest.raises(ValidationError) as raised:
        accounts.access_token(sender())
    assert "secret provider response" not in str(raised.value)


def test_token_refresh_request_has_explicit_timeout(accounts, monkeypatch):
    request = MagicMock(return_value="response")
    monkeypatch.setattr(accounts_module, "Request", lambda: request)
    assert accounts._request(url="https://provider.example", timeout=999) == "response"
    assert request.call_args.kwargs["timeout"] == 30


@pytest.mark.parametrize(
    "provider,code,body,expected",
    [
        ("google", 200, {"id": "synthetic-provider-id"}, Outcome.ACCEPTED),
        ("microsoft", 202, None, Outcome.ACCEPTED),
        ("google", 200, {}, Outcome.UNCERTAIN),
        ("google", 401, {}, Outcome.FAILED),
        ("microsoft", 403, {}, Outcome.FAILED),
        ("google", 429, {}, Outcome.RETRYABLE),
        ("google", 503, {}, Outcome.UNCERTAIN),
        ("google", 204, {}, Outcome.UNCERTAIN),
        ("microsoft", 400, {}, Outcome.FAILED),
        ("google", 302, {}, Outcome.FAILED),
    ],
)
def test_provider_send_preserves_reviewed_mime_and_maps_outcomes(
    accounts, rig, monkeypatch, provider, code, body, expected
):
    identity = sender(provider)
    rig.store.save_sender(identity)
    rig.store.add_contacts(rig.campaign, identity.id, [{"email": "recipient@example.com"}])
    message = rig.store.messages(rig.campaign)[0]
    rig.store.edit(message.id, "Exact reviewed subject", "Exact reviewed body", message.revision)
    rig.store.approve(message.id, rig.store.message(message.id).revision)
    message = rig.store.message(message.id)
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = httpx.Response(code, json=body)
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(mail_module.httpx, "Client", factory)
    outcome = OAuthMailTransport(accounts.settings, accounts).send(
        identity, "synthetic-token", message
    )
    assert outcome.outcome == expected
    assert factory.call_args.kwargs["follow_redirects"] is False
    call = client.post.call_args
    encoded = call.kwargs["json"]["raw"] if provider == "google" else call.kwargs["content"]
    mime = base64.urlsafe_b64decode(encoded).decode()
    assert "Exact reviewed subject" in mime and "Exact reviewed body" in mime
    assert "From: " + identity.email in mime and "To: recipient@example.com" in mime
    assert call.kwargs["headers"]["Authorization"] == "Bearer synthetic-token"
    assert call.args[0].startswith(
        "https://gmail.googleapis.com/" if provider == "google" else "https://graph.microsoft.com/"
    )


@pytest.mark.parametrize(
    "error,expected",
    [
        (httpx.ConnectError("private"), Outcome.RETRYABLE),
        (httpx.ConnectTimeout("private"), Outcome.RETRYABLE),
        (httpx.ReadTimeout("private"), Outcome.UNCERTAIN),
        (ValueError("private"), Outcome.UNCERTAIN),
    ],
)
def test_post_transmission_ambiguity_is_not_retried(accounts, rig, monkeypatch, error, expected):
    identity = sender()
    message = replace(rig.message(), sender_id=identity.id, sender_email=identity.email)
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.side_effect = error
    monkeypatch.setattr(mail_module.httpx, "Client", lambda **_: client)
    result = OAuthMailTransport(accounts.settings, accounts).send(identity, "synthetic", message)
    assert result.outcome == expected and "private" not in result.code
    assert client.post.call_count == 1


def test_transport_rejects_mismatched_sender_without_network(accounts, rig, monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(mail_module.httpx, "Client", client)
    result = OAuthMailTransport(accounts.settings, accounts).send(
        sender(), "synthetic", rig.message()
    )
    assert result.code == "authentication_failed"
    client.assert_not_called()


def microsoft_fakes(accounts, monkeypatch):
    app = MagicMock()
    app.initiate_auth_code_flow.return_value = {
        "auth_uri": "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
    }
    app.acquire_token_by_auth_code_flow.return_value = {
        "access_token": "synthetic-ms-token",
        "scope": "Mail.Send User.Read",
        "id_token_claims": {"tid": CONSUMER_TENANT, "oid": "personal-subject"},
    }
    app.get_accounts.return_value = [{"home_account_id": "personal-home"}]
    factory = MagicMock(return_value=app)
    monkeypatch.setattr(accounts_module.msal, "PublicClientApplication", factory)
    monkeypatch.setattr(accounts_module, "authorize_in_browser", fake_browser)
    client = MagicMock()
    client.__enter__.return_value = client
    client.get.return_value = httpx.Response(
        200,
        json={"mail": "person@outlook.com"},
        request=httpx.Request("GET", "https://graph.microsoft.com/v1.0/me"),
    )
    monkeypatch.setattr(httpx, "Client", lambda **_: client)
    return app, factory, client


def test_microsoft_consumer_browser_flow_and_primary_identity(accounts, monkeypatch):
    app, factory, client = microsoft_fakes(accounts, monkeypatch)
    data = accounts._microsoft_connect(Event())
    assert data["subject"] == "personal-subject" and data["email"] == "person@outlook.com"
    assert factory.call_args.kwargs["authority"] == CONSUMER_AUTHORITY
    assert factory.call_args.kwargs["enable_pii_log"] is False
    assert app.initiate_auth_code_flow.call_args.kwargs["prompt"] == "select_account"
    assert client.get.call_args.kwargs["headers"]["Authorization"] == "Bearer synthetic-ms-token"
    assert "Mail.Read" not in app.initiate_auth_code_flow.call_args.args[0]


@pytest.mark.parametrize(
    "failure",
    ["organization", "token", "subject", "permission", "multiple_accounts", "invalid_flow"],
)
def test_microsoft_rejects_organization_missing_grants_and_ambiguous_identity(
    accounts, monkeypatch, failure
):
    app, _, _ = microsoft_fakes(accounts, monkeypatch)
    result = app.acquire_token_by_auth_code_flow.return_value
    if failure == "organization":
        result["id_token_claims"]["tid"] = "organizational-tenant"
    elif failure == "token":
        result.pop("access_token")
    elif failure == "subject":
        result["id_token_claims"]["oid"] = ""
    elif failure == "permission":
        result["scope"] = "User.Read"
    elif failure == "multiple_accounts":
        app.get_accounts.return_value = []
    else:
        app.initiate_auth_code_flow.return_value = {}
    with pytest.raises(ValidationError):
        accounts._microsoft_connect(Event())


@pytest.mark.parametrize("changed", [False, True])
def test_microsoft_silent_refresh_uses_only_the_bound_cached_account(
    accounts, monkeypatch, changed
):
    accounts.secrets.save(sender("microsoft").id, session(accounts, "microsoft"))
    app, _, _ = microsoft_fakes(accounts, monkeypatch)
    cache = MagicMock(has_state_changed=changed)
    cache.serialize.return_value = "{}"
    monkeypatch.setattr(accounts_module.msal, "SerializableTokenCache", lambda: cache)
    app.acquire_token_silent_with_error.return_value = {"access_token": "synthetic-refreshed"}
    assert accounts.access_token(sender("microsoft")) == "synthetic-refreshed"
    assert app.acquire_token_silent_with_error.call_args.kwargs["account"] == {
        "home_account_id": "personal-home"
    }
    app.acquire_token_silent_with_error.return_value = None
    with pytest.raises(ValidationError, match="expired"):
        accounts.access_token(sender("microsoft"))


@pytest.mark.parametrize("failure", ["registration", "account", "cache"])
def test_microsoft_cached_authorization_failures_require_sign_in(accounts, monkeypatch, failure):
    data = session(accounts, "microsoft")
    if failure == "registration":
        data["client_id"] = "wrong"
    elif failure == "cache":
        data["cache"] = "invalid-json"
    accounts.secrets.save(sender("microsoft").id, data)
    app, _, _ = microsoft_fakes(accounts, monkeypatch)
    app.get_accounts.return_value = []
    with pytest.raises(ValidationError):
        accounts.access_token(sender("microsoft"))


@pytest.mark.parametrize("provider", ["google", "microsoft"])
def test_changed_subject_cannot_replace_existing_sender(accounts, rig, monkeypatch, provider):
    identity = sender(provider)
    rig.store.save_sender(identity)
    data = session(accounts, provider)
    data["subject"] = "other-person"
    monkeypatch.setattr(accounts, "_" + provider + "_connect", lambda _: data)
    with pytest.raises(ValidationError, match="same account"):
        accounts.connect(provider, Event(), identity.id)


def test_failed_sender_persistence_removes_new_authorization(accounts, monkeypatch):
    data = session(accounts)
    monkeypatch.setattr(accounts, "_google_connect", lambda _: data)
    monkeypatch.setattr(
        accounts.store, "save_sender", MagicMock(side_effect=OSError("private database path"))
    )
    with pytest.raises(ValidationError) as raised:
        accounts.connect("google", Event())
    assert "private database path" not in str(raised.value)
    assert not any(key.startswith("oauth:") for key in accounts.secrets.credentials._values)


def test_sign_in_offline_is_rejected_without_opening_browser(accounts, monkeypatch):
    accounts.settings = replace(accounts.settings, network=False)
    start = MagicMock()
    monkeypatch.setattr(accounts, "_google_connect", start)
    with pytest.raises(ValidationError, match="Network access is disabled"):
        accounts.connect("google", Event())
    start.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "smtp"},
        {"subject": ""},
        {"subject": "x" * 256},
        {"username": "other@gmail.com"},
        {"email": "person@company.com", "username": "person@company.com"},
    ],
)
def test_oauth_sender_identity_is_validated(changes):
    with pytest.raises(ValidationError):
        replace(sender(), **changes).validate()


def test_browser_cancel_after_launch_is_bounded(socket_enabled, monkeypatch):
    stopped = Event()

    def open_browser(*args, **kwargs):
        stopped.set()
        return True

    monkeypatch.setattr(browser.webbrowser, "open", open_browser)
    with pytest.raises(ValidationError, match="cancelled"):
        browser.authorize_in_browser(lambda *_: "https://accounts.google.com/auth", stopped)


def test_disconnect_failure_still_blocks_the_existing_grant(accounts, monkeypatch):
    identity = sender()
    accounts.store.save_sender(identity)
    accounts.secrets.save(identity.id, session(accounts))
    monkeypatch.setattr(
        accounts.secrets,
        "delete",
        MagicMock(side_effect=ValidationError("OS vault delete unavailable")),
    )
    with pytest.raises(ValidationError, match="unavailable"):
        accounts.disconnect(identity.id)
    with pytest.raises(ValidationError, match="disconnected"):
        accounts.access_token(identity)
