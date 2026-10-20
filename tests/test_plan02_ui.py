from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QMessageBox, QScrollArea

from cold_mailer.bootstrap import Application
from cold_mailer.infrastructure.storage import Store
from cold_mailer.settings import Settings
from cold_mailer.ui.scrolling import SmoothScroll
from cold_mailer.ui.window import Window
from tests.conftest import Rig

pytestmark = pytest.mark.ui


def test_autosave_incomplete_draft_and_toggle_restart(qtbot, rig: Rig) -> None:
    original = rig.message()
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        window.subject.clear()
        window.subject.textEdited.emit("")
        window.body.setPlainText("Partial draft")
        assert app.store.claim(original.id, 100) is None
        qtbot.waitUntil(lambda: not window.dirty and window.saver.future is None, timeout=5000)
        saved = app.store.message(original.id)
        assert saved.subject == "" and saved.body == "Partial draft" and saved.approval is None
        assert app.store.revisions(original.id)[0]["origin"] == "autosave"
        window.autosave_toggle.setChecked(False)
        window.body.setPlainText("Manual draft")
        assert window.dirty and not window.autosave_timer.isActive()
        window.save_draft()
        assert not window.dirty
        window.motion_toggle.setChecked(True)
        assert all(not controller.enabled for controller in window.scrollers)
        window.smooth_toggle.setChecked(False)
        window.close()
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        assert not window.autosave_toggle.isChecked()
        assert window.motion_toggle.isChecked()
        assert app.store.message(original.id).body == "Manual draft"
        window.close()


def test_autosave_failure_preserves_editor_and_close_flushes(qtbot, rig: Rig, monkeypatch) -> None:
    message = rig.message()
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        save = app.store.save_draft
        monkeypatch.setattr(app.store, "save_draft", MagicMock(side_effect=OSError("full disk")))
        window.body.setPlainText("Do not lose this")
        window.autosave()
        qtbot.waitUntil(lambda: window.saver.future is None)
        assert window.dirty and "could not be saved" in window.state.text()
        assert window.body.toPlainText() == "Do not lose this"
        assert not window.autosave_timer.isActive()
        monkeypatch.setattr(app.store, "save_draft", save)
        window.close()
        qtbot.waitUntil(lambda: not window.pending_close or not window.dirty)
        assert Store(app.store.path).message(message.id).body == "Do not lose this"


def test_navigation_cannot_save_to_wrong_recipient(qtbot, rig: Rig) -> None:
    rig.message()
    rig.message("other@example.com")
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        assert window.current_message
        first = window.current_message.id
        window.body.setPlainText("Only for the first selected recipient")
        window.table.setCurrentIndex(window.proxy.index(1, 0))
        assert window.current_message.id == first
        qtbot.waitUntil(lambda: not window.dirty and window.saver.future is None)
        window.table.setCurrentIndex(window.proxy.index(1, 0))
        assert window.current_message and window.current_message.id != first
        assert window.body.toPlainText() != "Only for the first selected recipient"
        assert app.store.message(first).body == "Only for the first selected recipient"
        window.close()


def test_history_and_safe_tools(qtbot, rig: Rig, monkeypatch) -> None:
    message = rig.message()
    rig.service.run(rig.campaign, Event())
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.tabs.setCurrentWidget(window.history_page)
        history = window.history_page
        qtbot.waitUntil(lambda: history.future is None)
        assert len(history.rows) == 1
        history.table.setCurrentIndex(history.model.index(0, 0))
        assert message.body in history.preview.toPlainText()
        history.next()
        history.previous()
        history.search.setText("not-present")
        history.refresh()
        qtbot.waitUntil(lambda: history.future is None)
        assert not history.rows
        history.outcome.setCurrentIndex(1)
        history.search.clear()
        history.refresh()
        qtbot.waitUntil(lambda: history.future is None)
        assert len(history.rows) == 1
        window.focus_search()
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
        window.preview_message()
        window.show_revisions()
        monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
        window.keyboard_help()
        monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("Open settings", True))
        window.command_palette()
        assert window.tabs.currentIndex() == 2
        window.close()


def wheel(pixel: int = 0, angle: int = -120) -> QWheelEvent:
    return QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, pixel),
        QPoint(0, angle),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def test_smooth_wheel_pixel_passthrough_and_reduced_motion(qtbot) -> None:
    area = QScrollArea()
    qtbot.addWidget(area)
    from PySide6.QtWidgets import QWidget

    content = QWidget()
    content.setMinimumHeight(2400)
    area.setWidget(content)
    area.resize(400, 300)
    area.show()
    controller = SmoothScroll(area)
    QApplication.sendEvent(area.viewport(), wheel())
    qtbot.waitUntil(lambda: area.verticalScrollBar().value() >= 80)
    assert controller.eventFilter(area.viewport(), wheel(pixel=-5)) is False
    controller.enabled = False
    assert controller.eventFilter(area.viewport(), wheel()) is False
    controller.enabled = True
    area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
    assert controller.eventFilter(area.viewport(), wheel()) is False


def test_demo_has_no_live_provider_path(qtbot, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    with Application(Settings(tmp_path / "demo"), demo=True) as app:
        window = Window(app)
        qtbot.addWidget(window)
        assert "DEMO" in window.mode_badge.text() and not window.live.isEnabled()
        window.live.setChecked(True)
        assert not window.live.isChecked()
        window.generate()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        messages = app.store.messages(window.campaign_id())
        assert all(message.body for message in messages)
        for message in messages:
            app.store.approve(message.id, message.revision)
        window.send()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        assert all(row["code"] == "demo_simulated_no_transmission" for row in app.store.history())
        assert not window.live.isEnabled()
        window.close()


def test_workspace_recipes_views_variables_and_private_exports(
    qtbot, rig: Rig, tmp_path: Path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QFileDialog

    rig.message()
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        window.show_doctor = MagicMock(wraps=window.show_doctor)
        monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
        window.show_doctor()
        window.setup_checklist()
        window.search.setText("alex@example.com")
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("Alex view", True))
        window.save_view()
        window.search.clear()
        monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("Alex view", True))
        window.open_view()
        assert window.search.text() == "alex@example.com"
        monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("first_name", True))
        window.wrapper.clear()
        window.insert_variable()
        assert window.wrapper.toPlainText() == "{{ first_name }}"
        window.prompt.setPlainText("A reviewed fictional offer")
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("Offer", True))
        window.save_blueprint()
        window.save_blueprint()
        monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("Offer · version 2", True))
        window.use_blueprint()
        assert len(app.store.campaigns()) == 2
        assert app.store.campaigns()[0]["prompt"] == "A reviewed fictional offer"
        assert not app.store.messages(app.store.campaigns()[0]["id"])
        target = tmp_path / "support.zip"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(target), ""))
        window.support_bundle()
        assert target.is_file()
        target = tmp_path / "private.cmbak"
        monkeypatch.setattr(
            QInputDialog, "getText", lambda *args: ("synthetic backup passphrase", True)
        )
        window.backup_encrypted()
        qtbot.waitUntil(lambda: window.operation_thread is None, timeout=5000)
        assert target.is_file() and target.read_bytes().startswith(b"CMAILBACKUP")
        window.close()


def test_disabling_autosave_during_write_does_not_enqueue_later_edits(
    qtbot, rig: Rig, monkeypatch
) -> None:
    from threading import Event

    rig.message()
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        original_save = app.store.save_draft
        started, release = Event(), Event()

        def delayed_save(*args, **kwargs):
            started.set()
            assert release.wait(5)
            return original_save(*args, **kwargs)

        monkeypatch.setattr(app.store, "save_draft", delayed_save)
        window.body.setPlainText("First snapshot")
        window.autosave()
        assert started.wait(2)
        window.body.setPlainText("Later unsaved edit")
        window.autosave_toggle.setChecked(False)
        release.set()
        qtbot.waitUntil(lambda: window.saver.future is None)
        assert window.dirty
        assert not window.autosave_timer.isActive()
        assert window.current_message and window.current_message.body == "First snapshot"
        monkeypatch.setattr(app.store, "save_draft", original_save)
        window.save_draft()
        window.close()


def test_editor_fields_do_not_overlap_when_page_requires_scrolling(qtbot, tmp_path: Path) -> None:
    with Application(Settings(tmp_path / "profile")) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.resize(1000, 650)
        window.show()
        QApplication.processEvents()
        container = window.instructions.parentWidget()
        assert container is not None
        body_end = window.body.mapTo(window.editor, QPoint(0, window.body.height())).y()
        instructions_start = container.mapTo(window.editor, QPoint(0, 0)).y()
        assert body_end <= instructions_start
        assert window.body.height() >= 126
        window.close()
