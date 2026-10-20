"""Read-only local runtime diagnostics. No credentials or network probes."""

import platform
import shutil
import sqlite3

from PySide6.QtCore import qVersion


def diagnostics() -> dict[str, object]:
    native = sqlite3.sqlite_version_info
    patched = (
        native >= (3, 51, 3)
        or (native[:2] == (3, 50) and native >= (3, 50, 7))
        or (native[:2] == (3, 44) and native >= (3, 44, 6))
    )
    return {
        "python": platform.python_version(),
        "platform": platform.system(),
        "qt": qVersion(),
        "sqlite": sqlite3.sqlite_version,
        "sqlite_wal_fix_present": patched,
        "journal_policy": "rollback; WAL disabled",
        "tools": {
            tool: bool(shutil.which(tool)) for tool in ("uv", "git", "ISCC", "MakeAppx", "SignTool")
        },
    }
