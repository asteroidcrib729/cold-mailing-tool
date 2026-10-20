import json
from pathlib import Path
from threading import Event

import pytest
from PySide6.QtWidgets import QMessageBox

from cold_mailer.bootstrap import Application
from cold_mailer.cli import main
from cold_mailer.infrastructure.credentials import MemoryCredentials
from cold_mailer.settings import Settings
from cold_mailer.ui.window import Window


@pytest.mark.integration
def test_cli_create_dry_run_offline_and_unknown_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    options = ["--data-dir", str(tmp_path / "profile")]
    assert main([*options, "diagnostics"]) == 0
    assert json.loads(capsys.readouterr().out)["network_enabled"] is False
    assert main([*options, "create", "Fixture"]) == 0
    campaign = json.loads(capsys.readouterr().out)["campaign"]
    assert main([*options, "dry-run", campaign]) == 0
    assert json.loads(capsys.readouterr().out) == {}
    assert main([*options, "run", campaign]) == 2
    assert "Network access is disabled" in capsys.readouterr().err


@pytest.mark.ui
def test_window_opens_without_credentials_and_real_widget_edit_review_flow(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cold_mailer.domain.models import Sender, Status

    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Ok)
    with Application(Settings(tmp_path / "profile")) as app:
        app.credentials = MemoryCredentials()
        sender = Sender(
            "sender", "sender@example.com", "smtp.example.com", 587, "sender", interval=0
        )
        app.store.save_sender(sender)
        campaign = app.store.create_campaign("Example")
        app.store.add_contacts(
            campaign, sender.id, [{"email": "alex@example.com", "first_name": "Alex"}]
        )
        window = Window(app)
        qtbot.addWidget(window)
        window.show()
        assert not window.live.isChecked()
        assert window.model.rowCount() == 1
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        window.select_message()
        window.subject.setText("Subject")
        window.body.setPlainText("Reviewed final body")
        window.save_draft()
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        window.select_message()
        window.approve()
        assert app.store.messages(campaign)[0].status == Status.APPROVED
        assert window.operation_thread is None
        window.close()


@pytest.mark.ui
def test_worker_serializes_operations_and_completes_on_gui_thread(qtbot, tmp_path: Path) -> None:
    from cold_mailer.domain.models import ValidationError

    with Application(Settings(tmp_path / "profile")) as app:
        window = Window(app)
        qtbot.addWidget(window)
        released = Event()

        def operation(stop, emit):
            emit("fixture worker started")
            released.wait(2)
            return {"complete": True}

        window.start(operation)
        with pytest.raises(ValidationError):
            window.start(operation)
        assert window.tabs.isEnabled()
        authoring = window.tabs.widget(0)
        settings = window.tabs.widget(2)
        assert authoring is not None and not authoring.isEnabled()
        assert settings is not None and settings.isEnabled()
        assert window.history_page.isEnabled()
        released.set()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        assert window.tabs.isEnabled()
        assert "complete" in window.log.toPlainText()
        window.close()
