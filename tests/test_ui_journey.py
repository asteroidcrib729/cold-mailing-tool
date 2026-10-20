from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from cold_mailer.bootstrap import Application
from cold_mailer.domain.models import Status, ValidationError
from cold_mailer.settings import Settings
from cold_mailer.ui import window as app_ui
from cold_mailer.ui.window import Window
from tests.conftest import Rig

pytestmark = pytest.mark.ui


def test_complete_workbench_journey(
    qtbot, rig: Rig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda parent, title, message: warnings.append(message)
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    with Application(Settings(rig.store.path.parent)) as app:
        app.credentials, app.service = rig.credentials, rig.service
        window = Window(app)
        qtbot.addWidget(window)
        window.show()
        window.model_name.setText("chosen-model")
        window.api_key.setText("synthetic-api-key")
        window.save_ai()
        assert app.credentials.get("google-api-key") == "synthetic-api-key"
        assert not window.api_key.text()
        assert app.store.preference("model") == "chosen-model"

        window.sender_fields["Email"].setText("extra@example.com")
        window.sender_fields["SMTP host"].setText("smtp.example.com")
        window.sender_fields["Username"].setText("extra")
        window.sender_fields["Password"].setText("synthetic-password")
        window.save_sender()
        assert len(app.store.senders()) == 2
        window.select_sender()
        window.delete_sender()
        assert len(app.store.senders()) == 1
        window.new_sender()
        assert not window.sender_fields["Email"].text()

        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("UI campaign", True))
        window.new_campaign()
        campaign = window.campaign_id()
        window.prompt.setPlainText("Facts only")
        window.wrapper.setPlainText("Hi {{ first_name }}, {{ AI_GENERATED_BODY }}")
        window.save_campaign()
        contacts = tmp_path / "ui.csv"
        contacts.write_text("email,first_name\nalex@example.com,Alex\ninvalid,Reject\n")
        monkeypatch.setattr(
            QInputDialog, "getItem", lambda parent, title, label, items, *args: (items[0], True)
        )
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(contacts), ""))
        window.import_contacts()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        assert len(app.store.messages(campaign)) == 1
        window.generate()
        assert warnings and "live mode" in warnings[-1]

        window.live.setChecked(True)
        fixture_ai = MagicMock()
        fixture_ai.generate.return_value = ("A subject", "A body")
        monkeypatch.setattr(app_ui, "AIGenerator", MagicMock(return_value=fixture_ai))
        window.generate()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        message = app.store.messages(campaign)[0]
        assert message.body == "Hi Alex, A body"
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        window.select_message()
        window.approve()
        window.dry_run()
        assert not rig.mail.messages
        monkeypatch.setattr(app_ui, "SMTPTransport", MagicMock(return_value=rig.mail))
        window.send()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        assert app.store.message(message.id).status == Status.ACCEPTED
        assert len(rig.mail.messages) == 1
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        window.select_message()
        assert window.body.isReadOnly()

        window.suppression.setText("future@example.com")
        window.suppress()
        assert "future@example.com" in app.store.suppressed()
        window.domain.setText("example.com")
        monkeypatch.setattr(
            app_ui, "domain_health", lambda domain: {"spf": "present", "dmarc": "unknown"}
        )
        window.check_domain()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        backup = tmp_path / "ui-backup.sqlite3"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(backup), ""))
        window.backup()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        assert backup.is_file()
        window.close()


def test_ui_validation_and_uncertain_recovery(
    qtbot, rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda parent, title, message: warnings.append(message)
    )
    with Application(Settings(rig.store.path.parent)) as app:
        app.credentials, app.service = rig.credentials, rig.service
        message = rig.message()
        rig.store.claim(message.id, 1000)
        app.recovered = rig.store.recover()
        window = Window(app)
        qtbot.addWidget(window)
        assert "uncertain" in window.state.text()
        window.approve()
        window.save_draft()
        window.reconcile()
        assert len(warnings) == 3
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        window.select_message()
        monkeypatch.setattr(
            QInputDialog, "getItem", lambda parent, title, label, items, *args: (items[1], True)
        )
        window.reconcile()
        assert rig.store.message(message.id).status == Status.DRAFT
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        window.select_message()
        window.body.setPlainText("Changed")
        window.approve()
        assert "Save message edits" in warnings[-1]
        window.live.setChecked(True)
        window.send()
        assert "Save or discard" in warnings[-1]
        window.check_domain()
        assert "plain domain" in warnings[-1]
        window.dirty = False
        window.close()


def test_worker_failure_stop_and_close_do_not_orphan_thread(qtbot, rig: Rig) -> None:
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)

        def operation(stop, emit):
            stop.wait(2)
            raise ValidationError("Synthetic cancellable failure")

        window.start(operation)
        window.close()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        assert "Synthetic cancellable failure" in window.log.toPlainText()


def test_ui_guard_sanitizes_unexpected_errors(qtbot, rig: Rig) -> None:
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)

        def fail():
            raise RuntimeError("private provider secret")

        from unittest.mock import patch

        with patch.object(QMessageBox, "warning") as warning:
            window.guard(fail)
            assert "private provider secret" not in str(warning.call_args)
        window.close()


def test_completion_waits_for_native_cleanup_without_blocking_close(
    qtbot, rig: Rig, monkeypatch
) -> None:
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.start(lambda stop, emit: "done")
        thread = window.operation_thread
        assert thread is not None
        original_wait = thread.wait
        checks = []

        def delayed_join(milliseconds: int) -> bool:
            checks.append(
                (milliseconds, window.operation_thread is thread, window.tabs.isEnabled())
            )
            return False if len(checks) == 1 else original_wait(milliseconds)

        monkeypatch.setattr(thread, "wait", delayed_join)
        window.close()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        assert len(checks) >= 2
        assert checks[0] == (0, True, False)
        assert not window.isVisible()
