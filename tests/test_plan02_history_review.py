import csv
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QFileDialog

from cold_mailer.bootstrap import Application
from cold_mailer.cli import parser
from cold_mailer.domain.models import ValidationError
from cold_mailer.infrastructure.history import export_history
from cold_mailer.settings import Settings
from cold_mailer.ui.window import Window
from tests.conftest import Rig


def sent_at(rig: Rig, when: float) -> None:
    message = rig.message()
    attempt = rig.store.claim(message.id, when)
    assert attempt
    rig.store.finish(message.id, attempt, "accepted", "fixture", when + 1)


def test_history_time_boundaries_and_reader_does_not_take_writer_lock(rig: Rig) -> None:
    sent_at(rig, 100)
    assert len(rig.store.history(since=100, until=101)) == 1
    assert not rig.store.history(since=101)
    assert not rig.store.history(until=100)
    for lower, upper in ((float("nan"), None), (10, 10), (11, 10)):
        with pytest.raises(ValidationError):
            rig.store.history(since=lower, until=upper)
    # A reader can finish while another thread owns the Store writer mutex.
    with ThreadPoolExecutor(max_workers=1) as executor, rig.store.connection():
        assert len(executor.submit(rig.store.history).result(timeout=2)) == 1


def test_cancelled_and_failed_exports_never_publish_partial_file(
    rig: Rig, tmp_path: Path, monkeypatch
) -> None:
    sent_at(rig, 100)
    target = tmp_path / "export.csv"
    with pytest.raises(ValidationError):
        export_history(rig.store, target, cancelled=lambda: True)
    assert not target.exists() and not list(tmp_path.glob("mail-export-*"))
    original = rig.store.history
    calls = 0

    def fails_after_page(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise sqlite3.OperationalError("synthetic read error")
        return original(*args, **kwargs)

    monkeypatch.setattr(rig.store, "history", fails_after_page)
    with pytest.raises(sqlite3.OperationalError):
        export_history(rig.store, target)
    assert not target.exists() and not list(tmp_path.glob("mail-export-*"))


def test_cli_history_requires_explicit_timezone_and_uses_exclusive_end() -> None:
    args = parser().parse_args(
        ["history", "--since", "2026-10-20T05:00:00+05:00", "--until", "2026-10-21T00:00:00Z"]
    )
    assert args.since == datetime(2026, 10, 20, tzinfo=UTC).timestamp()
    for value in ("2026-10-20", "2026-10-20T00:00:00", "invalid"):
        with pytest.raises(SystemExit):
            parser().parse_args(["history", "--since", value])


@pytest.mark.ui
def test_history_local_dates_dst_and_background_export(
    qtbot, rig: Rig, tmp_path: Path, monkeypatch
) -> None:
    sent_at(rig, datetime(2026, 3, 8, 7, 30, tzinfo=UTC).timestamp())
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        history = window.history_page
        history.timezone.setText("America/New_York")
        history.use_dates.setChecked(True)
        history.from_date.setDate(QDate(2026, 3, 8))
        history.to_date.setDate(QDate(2026, 3, 8))
        query = history.query()
        assert query.until is not None and query.since is not None
        assert query.until - query.since == 23 * 3600
        history.refresh()
        qtbot.waitUntil(lambda: history.future is None)
        assert len(history.rows) == 1
        assert "03:30:00-04:00" in history.model.item(0, 0).text()
        history.table.setCurrentIndex(history.model.index(0, 0))
        assert "America/New_York" in history.preview.toPlainText()
        target = tmp_path / "selected.csv"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(target), ""))
        history.export()
        qtbot.waitUntil(lambda: window.operation_thread is None)
        assert "Exported 1" in history.count.text()
        with target.open(encoding="utf-8-sig", newline="") as stream:
            assert next(csv.DictReader(stream))["started_utc"].endswith("+00:00")
        history.from_date.setDate(QDate(2026, 3, 9))
        history.refresh()
        assert "must not precede" in history.count.text()
        history.timezone.setText("unknown")
        history.refresh()
        assert "valid IANA" in history.count.text()
        window.close()


@pytest.mark.ui
def test_history_coalesces_pending_searches_and_discards_stale_results(
    qtbot, rig: Rig, monkeypatch
) -> None:
    sent_at(rig, 100)
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        history = window.history_page
        started, release = Event(), Event()
        original = app.store.history
        queries = []

        def delayed(query="", *args, **kwargs):
            queries.append(query)
            if query == "first":
                started.set()
                assert release.wait(3)
            return original(query, *args, **kwargs)

        monkeypatch.setattr(app.store, "history", delayed)
        history.search.setText("first")
        history.refresh()
        assert started.wait(2)
        for query in ("replaced", "also replaced", "reviewed"):
            history.search.setText(query)
            history.refresh()
        history.previous()
        history.next()
        # GUI continues to process events while the read-only worker is delayed.
        window.set_theme("dark")
        release.set()
        qtbot.waitUntil(lambda: history.future is None)
        assert queries == ["first", "reviewed"] and len(history.rows) == 1
        monkeypatch.setattr(
            app.store,
            "history",
            lambda *args, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError()),
        )
        history.refresh()
        qtbot.waitUntil(lambda: history.future is None)
        assert "Narrow" in history.count.text() and history.table.isEnabled()
        window.close()
