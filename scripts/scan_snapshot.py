"""Gitleaks against publishable source/index files, excluding private local state."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required for source verification.")
    scanner = root / "reports" / "tools" / ("gitleaks.exe" if os.name == "nt" else "gitleaks")
    if not scanner.is_file():
        raise RuntimeError("Install pinned scanners with scripts/install_tools.py first.")
    command = [git, "ls-files", "-z", "--cached"]
    if not args.staged:
        command += ["--others", "--exclude-standard"]
    # Fixed Git operations; filenames remain individual argv values, never shell text.
    raw_names = subprocess.check_output(command, cwd=root, timeout=30)  # nosec B603
    names = set(raw_names.decode().split("\x00"))
    report = root / "reports" / "snapshot-secrets.json"
    with tempfile.TemporaryDirectory(prefix="source-scan-", dir=root / "reports") as folder:
        snapshot = Path(folder)
        for name in sorted(names - {""}):
            path = root / name
            if not args.staged and not path.is_file():
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise RuntimeError("Source snapshot cannot include external or symbolic paths.")
            if path.name in {
                ".env",
                "secret.key",
                "config.db",
                "Load Contacts.csv",
            } or path.suffix in {".db", ".key", ".sqlite3"}:
                raise RuntimeError(f"Private runtime file is in the intended snapshot: {name}")
            if args.staged:
                content = subprocess.check_output([git, "show", ":" + name], cwd=root, timeout=30)  # nosec B603
            else:
                content = path.read_bytes()
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        # The scanner executable is pinned/verified by install_tools.py; no shell is used.
        result = subprocess.run(  # nosec B603
            [
                str(scanner),
                "dir",
                "--redact",
                "--no-banner",
                "--log-level",
                "error",
                "--report-format",
                "json",
                "--report-path",
                str(report),
                str(snapshot),
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )
        (root / "reports" / "snapshot-scanner.log").write_bytes(result.stdout + result.stderr)
    if result.returncode not in {0, 1}:
        raise RuntimeError("Secret scanner could not complete. Inspect the private local report.")
    findings = json.loads(report.read_text(encoding="utf-8"))
    print(f"Publishable snapshot scan: {len(findings)} redacted finding(s).")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
