"""Resolve an optional existing version tag to an immutable source commit."""

import argparse
import json
import re
import shutil
import subprocess  # nosec B404
import tomllib
from pathlib import Path


def windows_version(version: str) -> str:
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version):
        raise ValueError("Windows preview packaging requires a numeric MAJOR.MINOR.PATCH version")
    parts = [int(part) for part in version.split(".")]
    if any(part > 65535 for part in parts):
        raise ValueError("Windows version components must not exceed 65535")
    return version + ".0"


def resolve(root: Path, release_tag: str = "") -> dict[str, str]:
    git = shutil.which("git")
    if not git:
        raise ValueError("Git is required")
    if release_tag and not re.fullmatch(
        r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", release_tag
    ):
        raise ValueError("Use an existing vMAJOR.MINOR.PATCH tag or leave release_tag blank")
    ref = f"refs/tags/{release_tag}^{{commit}}" if release_tag else "HEAD"
    # The Git executable is resolved locally and ref is fixed or a validated numeric version tag.
    sha = subprocess.check_output(  # nosec B603
        [git, "rev-parse", "--verify", ref], cwd=root, timeout=30, text=True
    ).strip()
    raw = (
        # Resolved Git, validated tag/commit, fixed argument list, no shell.
        subprocess.check_output(  # nosec B603
            [git, "show", f"{sha}:pyproject.toml"], cwd=root, timeout=30, text=True
        )
        if release_tag
        else (root / "pyproject.toml").read_text(encoding="utf-8")
    )
    version = tomllib.loads(raw)["project"]["version"]
    native = windows_version(version)
    if release_tag and release_tag != "v" + version:
        raise ValueError("Release tag must match the version in that commit's pyproject.toml")
    return {
        "source_sha": sha,
        "version": version,
        "windows_version": native,
        "release_tag": release_tag,
        "distribution": "unsigned-preview",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-tag", default="")
    parser.add_argument("--output", type=Path, default=Path("reports/release-metadata.json"))
    args = parser.parse_args()
    metadata = resolve(Path(__file__).resolve().parents[1], args.release_tag)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
