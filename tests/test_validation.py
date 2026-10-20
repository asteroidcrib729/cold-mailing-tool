from dataclasses import replace
from pathlib import Path

import pytest
from openpyxl import Workbook

from cold_mailer.domain.models import Sender, ValidationError, address, header, validate_content
from cold_mailer.infrastructure.contacts import load_contacts, parse_rows
from cold_mailer.infrastructure.templates import render_template
from cold_mailer.settings import Settings

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-email",
        "a@example.com,b@example.com",
        "a@b",
        ".a@example.com",
        "a..b@example.com",
        "a@-example.com",
        "x\r\nBcc: b@example.com",
        "Name <a@example.com>",
        "a@exämple.com",
    ],
)
def test_reject_invalid_single_recipient(value: str) -> None:
    with pytest.raises(ValidationError):
        address(value)


def test_address_preserves_local_case_normalizes_domain() -> None:
    assert address("  Alex@EXAMPLE.COM ") == "Alex@example.com"


@pytest.mark.parametrize(
    "subject,body",
    [
        ("", "body"),
        ("hello\nbcc", "body"),
        ("hello", ""),
        ("hello", "[[AI unavailable]]"),
        ("{{ name }}", "body"),
        ("hello", "bad\x00body"),
        ("x" * 999, "body"),
    ],
)
def test_unsendable_content(subject: str, body: str) -> None:
    with pytest.raises(ValidationError):
        validate_content(subject, body)


def test_restricted_template() -> None:
    assert (
        render_template(
            "Hi {{ first_name }}, {{ AI_GENERATED_BODY }}",
            {"first_name": "Alex", "AI_GENERATED_BODY": "A body"},
        )
        == "Hi Alex, A body"
    )
    for template in [
        "{{ missing }}",
        "{{ x.__class__ }}",
        "{% for x in range(1000000) %}x{% endfor %}",
        "{{ 'x' * 1000000 }}",
        "{% if x %}yes{% endif %}",
    ]:
        with pytest.raises(ValidationError):
            render_template(template, {"x": "data"})


def test_import_accounting_and_string_values() -> None:
    report = parse_rows(
        [
            [" Email ", "first_name", "code"],
            ["a@example.com", "A", "001"],
            ["b@example.com", "B", "002"],
            ["bad", None, None],
            ["a@example.com", "dup", ""],
            ["skip@example.com", "S", ""],
        ],
        {"skip@example.com"},
    )
    assert len(report.contacts) == 2
    assert report.contacts[0]["code"] == "001"
    assert len(report.issues) == report.duplicates == report.suppressed == 1


@pytest.mark.parametrize("rows", [[], [["name"]], [["email", "email"]], [["email", ""]]])
def test_missing_or_ambiguous_headers(rows: list[list[str]]) -> None:
    with pytest.raises(ValidationError):
        parse_rows(rows)


def test_csv_and_xlsx(tmp_path: Path) -> None:
    csv = tmp_path / "contacts.csv"
    csv.write_text('\ufeffemail,first_name\na@example.com,"Alex\nExample"\n', encoding="utf-8")
    assert load_contacts(csv).contacts[0]["first_name"] == "Alex\nExample"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["email", "first_name"])
    sheet.append(["b@example.com", "Bee"])
    xlsx = tmp_path / "contacts.xlsx"
    workbook.save(xlsx)
    workbook.close()
    assert load_contacts(xlsx).contacts[0]["email"] == "b@example.com"
    bad = tmp_path / "contacts.xls"
    bad.write_text("not-supported")
    with pytest.raises(ValidationError):
        load_contacts(bad)
    with pytest.raises(ValidationError):
        load_contacts(tmp_path / "missing.csv")


def test_profile_settings_are_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("GENAI_MODEL=fixture-model\nAPI_KEY=synthetic-key\n")
    monkeypatch.delenv("GENAI_MODEL", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    settings = Settings.load(tmp_path / "profile")
    assert settings.model == settings.api_key == ""
    assert not settings.data_dir.exists()
    with pytest.raises(ValidationError):
        settings.require_network()
    explicit = Settings.load(tmp_path / "profile", development=True)
    assert explicit.model == "fixture-model"
    assert "synthetic-key" not in repr(explicit)


@pytest.mark.parametrize(
    "sender",
    [
        replace(Sender("a", "a@example.com", "smtp.example.com", 587, "a"), port=0),
        replace(Sender("a", "a@example.com", "smtp.example.com", 587, "a"), host="smtp/invalid"),
        replace(Sender("a", "a@example.com", "smtp.example.com", 587, "a"), tls="none"),
        replace(Sender("a", "a@example.com", "smtp.example.com", 587, "a"), daily_limit=0),
        replace(Sender("a", "a@example.com", "smtp.example.com", 587, "a"), interval=-1),
    ],
)
def test_sender_constraints(sender: Sender) -> None:
    with pytest.raises(ValidationError):
        sender.validate()


def test_header_and_template_bounds() -> None:
    assert header(" subject ") == "subject"
    with pytest.raises(ValidationError):
        render_template("a" * 20001, {})
