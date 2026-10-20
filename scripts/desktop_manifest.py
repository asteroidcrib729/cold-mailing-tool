"""Development artifact identity; dirty source is explicitly labelled unsigned preview."""

import hashlib
import json
import shutil
import subprocess  # nosec B404
import tomllib
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required for source verification.")
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    executable = root / "dist" / "desktop" / "ColdMailer" / "ColdMailer.exe"
    # Fixed Git argument lists, resolved executable, and no shell or credential arguments.
    head = subprocess.check_output([git, "rev-parse", "HEAD"], cwd=root, timeout=30)  # nosec B603
    dirty = subprocess.check_output([git, "status", "--porcelain"], cwd=root, timeout=30)  # nosec B603
    manifest = {
        "version": config["project"]["version"],
        "source_commit": head.decode().strip(),
        "working_tree_dirty": bool(dirty),
        "release_status": "unsigned development preview; not release certified",
        "executable_sha256": digest(executable),
        "lockfile_sha256": digest(root / "uv.lock"),
        "source_sha256": {
            path.relative_to(root).as_posix(): digest(path)
            for path in sorted((root / "src" / "cold_mailer").rglob("*"))
            if path.is_file() and path.suffix in {".py", ".svg"}
        },
    }
    target = root / "dist" / "desktop" / "development-manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
