"""Launch an explicitly chosen workspace without inheriting API credentials or import paths."""

import os
import subprocess  # nosec B404
import sys
from pathlib import Path

from cold_mailer.domain.models import ValidationError


def launch_workspace(directory: Path) -> subprocess.Popen[bytes]:
    directory = directory.resolve()
    if not directory.is_dir() or (
        any(directory.iterdir()) and not (directory / "campaigns.sqlite3").is_file()
    ):
        raise ValidationError(
            "Choose an empty folder or an existing Cold Mailer workspace containing campaigns.sqlite3."
        )
    executable = Path(sys.executable)
    if getattr(sys, "frozen", False):
        command = [str(executable), "--data-dir", str(directory)]
    else:
        windowed = executable.with_name("pythonw.exe")
        if sys.platform == "win32" and windowed.is_file():
            executable = windowed
        command = [str(executable), "-I", "-m", "cold_mailer.ui", "--data-dir", str(directory)]
    environment = dict(os.environ)
    for key in ("GOOGLE_GENAI_API_KEY", "GOOGLE_API_KEY", "API_KEY", "PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    # Fixed executable/argument list, no shell, no live flag, and a reviewed local directory.
    return subprocess.Popen(
        command,
        cwd=directory,
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )  # nosec B603
