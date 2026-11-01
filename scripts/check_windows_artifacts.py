"""Verify preview package identity and exact frozen payload bytes without installing trust."""

import hashlib
import json
import os
import tomllib
import zipfile
from pathlib import Path
from xml.dom import minidom  # nosec B408

from scripts.release_metadata import windows_version


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify(root: Path) -> dict[str, object]:
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    payload = root / "dist/desktop/ColdMailer"
    for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
        if (payload / name).read_bytes() != (root / name).read_bytes():
            raise ValueError(f"Desktop licensing file is missing or outdated: {name}")
    installers = root / "dist/installers"
    msix = installers / f"ColdMailer-{version}-x64-unsigned.msix"
    manifest = json.loads((installers / "development-manifest.json").read_text(encoding="utf-8"))
    if manifest["executable_sha256"] != digest((payload / "ColdMailer.exe").read_bytes()):
        raise ValueError("Desktop executable no longer matches its source manifest")
    for name, expected in manifest["source_sha256"].items():
        if digest((root / name).read_bytes()) != expected:
            raise ValueError(f"Source changed after the frozen build: {name}")
    with zipfile.ZipFile(msix) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate MSIX payload paths")
        raw_manifest = archive.read("AppxManifest.xml")
        if (
            b"<!DOCTYPE" in raw_manifest.upper()
            or b"<!ENTITY" in raw_manifest.upper()
            or len(raw_manifest) > 100_000
        ):
            raise ValueError("Unexpected manifest XML declarations/size")
        # Only a locally generated package is accepted here; DTD/entity input is rejected above.
        document = minidom.parseString(raw_manifest)  # nosec B318
        identity = document.getElementsByTagName("Identity")[0]
        expected_identity = {
            "Name": "ColdMailer.Preview",
            "Publisher": "CN=ColdMailerPreview",
            "Version": windows_version(version),
            "ProcessorArchitecture": "x64",
        }
        if any(identity.getAttribute(key) != value for key, value in expected_identity.items()):
            raise ValueError("MSIX identity/version mismatch")
        for name in (
            "ColdMailer.exe",
            "LICENSE",
            "NOTICE",
            "THIRD_PARTY_NOTICES.md",
            "_internal/sqlite3.dll",
            *[
                "_internal/cold_mailer/ui/assets/" + item.name
                for item in (root / "src/cold_mailer/ui/assets").glob("*.svg")
            ],
        ):
            if archive.read(name) != (payload / name).read_bytes():
                raise ValueError(f"MSIX payload mismatch: {name}")
        for name in names:
            parts = Path(name).parts
            if any(
                part in {".env", "secret.key", "config.db", "tests", "reports"} for part in parts
            ) or name.endswith((".sqlite3", ".bak")):
                raise ValueError(f"Private or development data in MSIX: {name}")
    sums = {}
    for line in (installers / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
        checksum, name = line.split("  ", 1)
        if Path(name).name != name or digest((installers / name).read_bytes()) != checksum:
            raise ValueError("Installer checksum mismatch")
        sums[name] = checksum
    if not any(name.endswith("-setup.exe") for name in sums) or msix.name not in sums:
        raise ValueError("Both installer types must appear in checksums")
    return {
        "version": version,
        "identity": expected_identity,
        "payload_files": len(names),
        "checksums": sums,
        "source_matches": True,
        "msix_signature": "unsigned preview; no install trust configured",
        "build_tools": {
            "inno_setup_version": "6.7.3",
            "inno_compiler_sha256": digest(
                (root / "reports/tools/inno-6.7.3/ISCC.exe").read_bytes()
            ),
            "windows_sdk": "10.0.26100.0",
            "makeappx_sha256": digest(
                (
                    Path(os.environ["PROGRAMFILES(X86)"])
                    / "Windows Kits/10/bin/10.0.26100.0/x64/makeappx.exe"
                ).read_bytes()
            ),
            "bundled_sqlite_sha256": digest((payload / "_internal/sqlite3.dll").read_bytes()),
        },
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    report = verify(root)
    (root / "reports/windows-artifact-verification.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
