from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
)

from cold_mailer.bootstrap import Application
from cold_mailer.settings import Settings
from cold_mailer.ui import theme
from cold_mailer.ui.window import Window
from tests.conftest import Rig

pytestmark = pytest.mark.ui


@pytest.mark.parametrize("mode", ["light", "dark", "system"])
def test_theme_preference_is_shared_and_survives_restart(qtbot, tmp_path: Path, mode: str) -> None:
    settings = Settings(tmp_path / "profile")
    with Application(settings) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.set_theme("dark" if mode == "light" else "light")
        window.settings_theme.setCurrentIndex(window.settings_theme.findData(mode))
        assert window.theme_selector.currentData() == mode
        assert app.store.preference("appearance.theme") == mode
        assert not window.live.isChecked()
        window.close()
    with Application(settings) as app:
        reopened = Window(app)
        qtbot.addWidget(reopened)
        assert reopened.theme_mode == mode
        assert reopened.settings_theme.currentData() == mode
        assert reopened.property("resolvedTheme") == theme.resolve_theme(mode)
        reopened.close()


def test_system_theme_tracks_changes_but_explicit_choice_stays_fixed(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    with Application(Settings(tmp_path / "profile")) as app:
        window = Window(app)
        qtbot.addWidget(window)
        real_resolve = theme.resolve_theme
        monkeypatch.setattr(
            theme, "resolve_theme", lambda mode: "dark" if mode == "system" else real_resolve(mode)
        )
        window.set_theme("system")
        assert window.property("resolvedTheme") == "dark"
        monkeypatch.setattr(theme, "resolve_theme", lambda mode: "light")
        window.system_theme_changed()
        assert window.property("resolvedTheme") == "light"
        monkeypatch.setattr(theme, "resolve_theme", real_resolve)
        window.set_theme("dark")
        window.system_theme_changed()
        assert window.property("resolvedTheme") == "dark"
        window.close()


def test_failed_preference_save_restores_selectors_and_preserves_edits(
    qtbot, rig: Rig, monkeypatch
) -> None:
    message = rig.message()
    with Application(Settings(rig.store.path.parent)) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.table.setCurrentIndex(window.proxy.index(0, 0))
        window.select_message()
        assert not window.dirty
        window.set_theme("dark")
        assert not window.dirty
        window.body.setPlainText("Unsaved personal draft")
        assert window.dirty and window.body.toPlainText() == "Unsaved personal draft"
        assert app.store.message(message.id).revision == message.revision
        monkeypatch.setattr(
            app.store, "save_preference", MagicMock(side_effect=OSError("private path"))
        )
        warning = MagicMock()
        monkeypatch.setattr(QMessageBox, "warning", warning)
        window.theme_selector.setCurrentIndex(window.theme_selector.findData("light"))
        assert window.theme_selector.currentData() == "dark"
        assert window.settings_theme.currentData() == "dark"
        assert "private path" not in str(warning.call_args)
        window.dirty = False
        window.close()


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("size", [(1000, 650), (1280, 720), (1440, 900)])
def test_controls_keep_usable_geometry_on_every_page(
    qtbot, tmp_path: Path, mode: str, size: tuple[int, int]
) -> None:
    with Application(Settings(tmp_path / "profile")) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.set_theme(mode)
        window.resize(*size)
        window.show()
        for page in range(3):
            window.tabs.setCurrentIndex(page)
            QApplication.processEvents()
            for button in window.findChildren(QPushButton):
                if button.isVisibleTo(window):
                    assert button.height() >= 38, button.text()
                    assert (
                        button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 20
                    ), button.text()
            controls = (
                [window.subject, window.body]
                if page == 0
                else [
                    *window.sender_fields.values(),
                    window.port,
                    window.tls,
                    window.limit,
                    window.interval,
                ]
                if page == 1
                else [
                    window.settings_theme,
                    window.model_name,
                    window.api_key,
                    window.domain,
                    window.suppression,
                ]
            )
            for control in controls:
                assert control.height() >= 38
            for combo in (window.theme_selector, window.campaign, window.senders, window.tls):
                option = QStyleOptionComboBox()
                option.initFrom(combo)
                arrow = combo.style().subControlRect(
                    QStyle.ComplexControl.CC_ComboBox,
                    option,
                    QStyle.SubControl.SC_ComboBoxArrow,
                    combo,
                )
                assert combo.rect().contains(arrow)
                assert arrow.width() >= 24
        expected = theme.DARK if mode == "dark" else theme.LIGHT
        assert window.palette().color(QPalette.ColorRole.Window).name() == expected.canvas
        window.tabs.setCurrentIndex(0)
        window.brief_toggle.click()
        QApplication.processEvents()
        assert not window.brief_tabs.isHidden()
        assert window.body.height() >= 126
        window.search.setText("Nobody matches")
        assert "No matching" in window.empty_title.text()
        window.search.clear()
        assert "conversation" in window.empty_title.text()
        window.close()


def test_dropdown_arrows_spin_buttons_and_live_checkbox_work(qtbot, tmp_path: Path) -> None:
    with Application(Settings(tmp_path / "profile")) as app:
        window = Window(app)
        qtbot.addWidget(window)
        window.set_theme("dark")
        window.tabs.setCurrentIndex(1)
        window.show()
        QApplication.processEvents()
        combo = window.tls
        option = QStyleOptionComboBox()
        option.initFrom(combo)
        arrow = combo.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxArrow, combo
        )
        qtbot.mouseClick(combo, Qt.MouseButton.LeftButton, pos=arrow.center())
        qtbot.waitUntil(lambda: combo.view().isVisible())
        qtbot.keyClick(combo, Qt.Key.Key_Down)
        qtbot.keyClick(combo, Qt.Key.Key_Return)
        assert combo.currentText() == "tls"
        spin = window.port
        assert spin.lineEdit().textMargins().left() >= 8
        option_spin = QStyleOptionSpinBox()
        spin.initStyleOption(option_spin)
        up = spin.style().subControlRect(
            QStyle.ComplexControl.CC_SpinBox, option_spin, QStyle.SubControl.SC_SpinBoxUp, spin
        )
        qtbot.mouseClick(spin, Qt.MouseButton.LeftButton, pos=up.center())
        assert spin.value() == 588
        qtbot.mouseClick(window.live, Qt.MouseButton.LeftButton)
        assert window.live.isChecked()
        assert window.mode_badge.property("live") is True
        assert app.settings.network is False
        window.close()
