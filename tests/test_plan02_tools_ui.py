import gc
import json
import sqlite3
import weakref
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, QThread
from PySide6.QtWidgets import QComboBox, QDialog, QFileDialog, QInputDialog, QMessageBox

from cold_mailer.bootstrap import Application
from cold_mailer.infrastructure.backup import encrypted_backup
from cold_mailer.infrastructure.storage import Store
from cold_mailer.settings import Settings
from cold_mailer.ui.callbacks import weak_callback
from cold_mailer.ui.window import Window
from tests.conftest import Rig
from tests.test_plan02_organization import feedback_file

pytestmark = pytest.mark.ui


def test_tools_policies_contrast_and_persistent_budget(qtbot, rig: Rig) -> None:
    rig.message()
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        tools = window.tools_page
        window.set_theme("contrast")
        assert window.property("resolvedTheme") == "contrast"
        tools.timezone.setText("invalid")
        tools.save_window()
        assert "valid IANA" in tools.status.text()
        assert not app.store.preference("sending.window")
        tools.timezone.setText("Asia/Karachi")
        tools.window_enabled.setChecked(True)
        tools.save_window()
        assert json.loads(app.store.preference("sending.window"))["timezone"] == "Asia/Karachi"
        tools.preview_window()
        assert "UTC" in tools.status.text()
        tools.contact_zone.setChecked(True)
        tools.preview_window()
        assert "Held" in tools.status.text()
        tools.per_run.setValue(2)
        tools.per_day.setValue(3)
        tools.price.setValue(0.25)
        tools.save_budget()
        tools.preview_budget()
        assert "0.500000" in tools.status.text()
        assert not rig.mail.messages
        window.close()
    with Application(Settings(rig.store.path.parent)) as app:
        reopened = Window(app)
        qtbot.addWidget(reopened)
        assert reopened.theme_mode == "contrast"
        assert reopened.tools_page.per_run.value() == 2
        reopened.close()


def test_revision_comparison_source_review_and_local_feedback(
    qtbot, rig: Rig, tmp_path: Path, monkeypatch
) -> None:
    original = rig.message()
    rig.store.edit(original.id, "Changed", "Changed body", original.revision)
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        tools = window.tools_page
        monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
        tools.show_sources()
        tools.show_report()
        monkeypatch.setattr(
            QInputDialog, "getItem", lambda parent, title, label, items, *args: (items[-1], True)
        )
        tools.restore_revision()
        restored = app.store.message(original.id)
        assert restored.body == original.body and restored.approval is None
        assert app.store.revisions(original.id)[0]["origin"] == "restored"
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        path = feedback_file(tmp_path / "reply.eml", original.message_id)
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), ""))

        def accept_feedback(dialog):
            for control in dialog.findChildren(QComboBox):
                if control.findText("optout") >= 0:
                    control.setCurrentText("optout")
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(QDialog, "exec", accept_feedback)
        tools.import_feedback()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        assert original.recipient in app.store.suppressed()
        assert app.store.message(original.id).status.value == "suppressed"
        assert not rig.mail.messages
        window.close()


def test_gui_restore_uses_new_workspace_and_holds_old_runs(
    qtbot, rig: Rig, tmp_path: Path, monkeypatch
) -> None:
    from cold_mailer.infrastructure.organization import Organization

    message = rig.message()
    Organization(rig.store).freeze(rig.campaign)
    backup = tmp_path / "private.cmbak"
    encrypted_backup(rig.store, backup, "synthetic recovery passphrase")
    before = rig.store.path.read_bytes()
    destination = tmp_path / "new-workspace" / "campaigns.sqlite3"
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(backup), ""))
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(destination), ""))
        monkeypatch.setattr(
            QInputDialog, "getText", lambda *args: ("synthetic recovery passphrase", True)
        )
        window.tools_page.restore_backup()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        restored = Store(destination)
        assert restored.message(message.id).status.value == "uncertain"
        with restored.connection() as conn:
            assert conn.execute("SELECT state FROM frozen_runs").fetchone()[0] == "restored_hold"
        assert rig.store.path.read_bytes() == before
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(rig.store.path), ""))
        window.tools_page.restore_backup()
        assert "NEW empty" in window.tools_page.status.text()
        window.close()


def test_campaign_autosave_replays_navigation_and_flushes_close(qtbot, rig: Rig) -> None:
    other = rig.store.create_campaign("Other", "Other facts", "{{ AI_GENERATED_BODY }}")
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.campaign.setCurrentIndex(window.campaign.findData(rig.campaign))
        window.prompt.setPlainText("Updated facts for the original campaign")
        assert window.campaign_dirty
        window.campaign.setCurrentIndex(window.campaign.findData(other))
        qtbot.waitUntil(
            lambda: window.loaded_campaign == other and window.saver.future is None, timeout=5000
        )
        assert (
            next(row for row in app.store.campaigns() if row["id"] == rig.campaign)["prompt"]
            == "Updated facts for the original campaign"
        )
        assert window.prompt.toPlainText() == "Other facts"
        window.prompt.setPlainText("Saved on close")
        window.close()
        qtbot.waitUntil(
            lambda: window.saver.future is None and not window.campaign_dirty, timeout=5000
        )
        assert (
            next(row for row in app.store.campaigns() if row["id"] == other)["prompt"]
            == "Saved on close"
        )


@pytest.mark.parametrize(
    "decision",
    [
        QMessageBox.StandardButton.Save,
        QMessageBox.StandardButton.Discard,
        QMessageBox.StandardButton.Cancel,
    ],
)
def test_manual_save_discard_cancel_keeps_recipient_and_campaign_consistent(
    qtbot, rig: Rig, monkeypatch, decision
) -> None:
    rig.message()
    rig.message("second@example.com")
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.autosave_toggle.setChecked(False)
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        assert window.current_message
        selected = window.current_message
        window.body.setPlainText("New body")
        window.prompt.setPlainText("New brief")
        monkeypatch.setattr(QMessageBox, "question", lambda *args: decision)
        window.table.setCurrentIndex(window.proxy.index(1, 0))
        assert window.current_message
        if decision == QMessageBox.StandardButton.Cancel:
            assert (
                window.current_message.id == selected.id and window.dirty and window.campaign_dirty
            )
        else:
            assert window.current_message.id != selected.id and not window.dirty
            expected = "New body" if decision == QMessageBox.StandardButton.Save else selected.body
            assert app.store.message(selected.id).body == expected
            assert window.prompt.toPlainText() == (
                "New brief" if decision == QMessageBox.StandardButton.Save else "A factual offer"
            )
        monkeypatch.setattr(
            QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard
        )
        window.close()


def test_actual_sqlite_readonly_save_failure_can_be_retried(qtbot, rig: Rig, monkeypatch) -> None:
    rig.message()
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        window.body.setPlainText("Keep this text after a storage failure")
        original = app.store.connection

        @contextmanager
        def readonly():
            with (
                closing(sqlite3.connect(app.store.path.as_uri() + "?mode=ro", uri=True)) as conn,
                conn,
            ):
                conn.row_factory = sqlite3.Row
                yield conn

        monkeypatch.setattr(app.store, "connection", readonly)
        window.autosave()
        qtbot.waitUntil(lambda: window.saver.future is None)
        assert window.dirty and "could not be saved" in window.state.text()
        assert window.body.toPlainText() == "Keep this text after a storage failure"
        monkeypatch.setattr(app.store, "connection", original)
        window.save_draft()
        assert not window.dirty
        window.close()


def test_callbacks_release_qt_owners_before_background_collection(qtbot) -> None:
    destroyed = []

    class Owner(QObject):
        def value(self) -> int:
            return 42

    owner = Owner()
    owner.destroyed.connect(lambda: destroyed.append(QThread.currentThread()))
    reference = weakref.ref(owner)
    callback = weak_callback(owner.value)
    assert callback() == 42
    del owner
    assert reference() is None
    assert destroyed == [QThread.currentThread()]
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(gc.collect).result(timeout=5)
    with pytest.raises(RuntimeError, match="closed"):
        callback()
    assert weak_callback(lambda: 7)() == 7


def test_workspace_launcher_uses_isolated_imports_without_api_credentials(
    tmp_path: Path, monkeypatch
) -> None:
    import cold_mailer.infrastructure.workspaces as workspaces

    directory = tmp_path / "workspace"
    directory.mkdir()
    process = MagicMock()
    launch = MagicMock(return_value=process)
    monkeypatch.setattr(workspaces.subprocess, "Popen", launch)
    monkeypatch.setenv("GOOGLE_GENAI_API_KEY", "synthetic-do-not-inherit")
    monkeypatch.setenv("PYTHONPATH", "untrusted-import-path")
    assert workspaces.launch_workspace(directory) is process
    args, kwargs = launch.call_args
    assert "-I" in args[0] and "--live" not in args[0]
    assert "GOOGLE_GENAI_API_KEY" not in kwargs["env"] and "PYTHONPATH" not in kwargs["env"]
    (directory / "unrelated.txt").write_text("unrelated")
    with pytest.raises(ValueError):
        workspaces.launch_workspace(directory)
