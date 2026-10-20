"""Install pinned, checksum-verified scanner binaries into ignored reports/tools."""

from __future__ import annotations

import hashlib
import io
import os
import tarfile
import urllib.request
import zipfile
from pathlib import Path

TOOLS = {
    "gitleaks": (
        "gitleaks/gitleaks",
        "8.30.1",
        "x64",
        {
            "windows": "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
            "linux": "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
        },
    ),
    "actionlint": (
        "rhysd/actionlint",
        "1.7.12",
        "amd64",
        {
            "windows": "6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9",
            "linux": "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
        },
    ),
}


def main() -> None:
    system = "windows" if os.name == "nt" else "linux"
    destination = Path(__file__).resolve().parents[1] / "reports" / "tools"
    destination.mkdir(parents=True, exist_ok=True)
    for tool, (repository, version, architecture, hashes) in TOOLS.items():
        suffix = "zip" if system == "windows" else "tar.gz"
        name = f"{tool}_{version}_{system}_{architecture}.{suffix}"
        url = f"https://github.com/{repository}/releases/download/v{version}/{name}"
        request = urllib.request.Request(url, headers={"User-Agent": "ColdMailer-tool-bootstrap"})
        with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != hashes[system]:
            raise RuntimeError(f"Checksum mismatch for {tool}; nothing was installed.")
        binary_name = tool + (".exe" if system == "windows" else "")
        if system == "windows":
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                binary = archive.read(binary_name)
        else:
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
                member = archive.extractfile(binary_name)
                if member is None:
                    raise RuntimeError(f"Missing binary for {tool}.")
                with member:
                    binary = member.read()
        target = destination / binary_name
        target.write_bytes(binary)
        target.chmod(0o755)
        print(f"Verified {tool} {version} -> {target}")


if __name__ == "__main__":
    main()
