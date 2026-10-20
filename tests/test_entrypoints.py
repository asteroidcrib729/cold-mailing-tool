from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from cold_mailer.ui import window as app_ui

pytestmark = pytest.mark.ui


def test_gui_entrypoint_isolated_smoke(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(QApplication, "exec", MagicMock(return_value=0))
    monkeypatch.setattr(QTimer, "singleShot", MagicMock())
    image = tmp_path / "snapshot.png"
    assert (
        app_ui.main(
            ["--smoke-test", "--data-dir", str(tmp_path / "profile"), "--snapshot", str(image)]
        )
        == 0
    )
    assert image.is_file()


def test_smoke_requires_explicit_profile() -> None:
    with pytest.raises(SystemExit) as result:
        app_ui.main(["--smoke-test"])
    assert result.value.code == 2
