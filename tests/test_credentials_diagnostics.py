from unittest.mock import MagicMock

import dns.resolver
import keyring
import pytest
from keyring.errors import KeyringError, PasswordDeleteError

from cold_mailer.domain.models import ValidationError
from cold_mailer.infrastructure.credentials import OSKeyring
from cold_mailer.infrastructure.dns import domain_health, txt_status

pytestmark = pytest.mark.unit


def test_os_credentials_errors_are_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    store = OSKeyring("synthetic-profile")
    monkeypatch.setattr(keyring, "get_password", MagicMock(return_value="synthetic"))
    monkeypatch.setattr(keyring, "set_password", MagicMock())
    monkeypatch.setattr(keyring, "delete_password", MagicMock())
    assert store.get("ref") == "synthetic"
    store.set("ref", "value")
    store.delete("ref")
    with pytest.raises(ValidationError):
        store.set("ref", "")
    for name, call in [
        ("get_password", lambda: store.get("ref")),
        ("set_password", lambda: store.set("ref", "value")),
        ("delete_password", lambda: store.delete("ref")),
    ]:
        monkeypatch.setattr(keyring, name, MagicMock(side_effect=KeyringError("private secret")))
        with pytest.raises(ValidationError) as error:
            call()
        assert "private secret" not in str(error.value)
    monkeypatch.setattr(keyring, "delete_password", MagicMock(side_effect=PasswordDeleteError()))
    store.delete("missing")


def test_dns_chunked_records_and_failure_states(monkeypatch: pytest.MonkeyPatch) -> None:
    record = MagicMock()
    record.strings = (b"v=spf", b"1 include:example.com")
    monkeypatch.setattr(dns.resolver, "resolve", MagicMock(return_value=[record]))
    assert txt_status("example.com", "v=spf1") == "present"
    assert domain_health("example.com")["dmarc"] == "missing"
    monkeypatch.setattr(dns.resolver, "resolve", MagicMock(side_effect=dns.resolver.NXDOMAIN()))
    assert txt_status("example.com", "v=spf1") == "missing"
    monkeypatch.setattr(dns.resolver, "resolve", MagicMock(side_effect=TimeoutError()))
    assert txt_status("example.com", "v=spf1") == "unknown"
