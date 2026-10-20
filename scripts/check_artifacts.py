"""Inspect archives by allowlist; never open a local credential/database file."""

import tarfile
import zipfile
from pathlib import Path


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = {
        path.relative_to(root / "src").as_posix()
        for path in (root / "src" / "cold_mailer").rglob("*")
        if path.is_file() and path.suffix in {".py", ".svg"}
    }
    require(bool(expected), "Application package is missing.")
    wheel = next((root / "dist").glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        files = archive.namelist()
        for name in expected:
            require(
                archive.read(name) == (root / "src" / name).read_bytes(),
                f"Wheel source differs from the current module: {name}",
            )
        require(
            {name for name in files if name.endswith((".py", ".svg"))} == expected,
            "Wheel modules differ from the allowlist.",
        )
        require(
            all(name in expected or ".dist-info/" in name for name in files),
            "Unexpected wheel contents.",
        )
    source = next((root / "dist").glob("*.tar.gz"))
    with tarfile.open(source) as archive:
        source_files = {
            "/".join(Path(member.name).parts[1:]): member
            for member in archive.getmembers()
            if member.isfile()
        }
        for name in expected:
            member = source_files.get("src/" + name)
            require(member is not None, f"Source archive omits package file: {name}")
            content = archive.extractfile(member) if member is not None else None
            require(content is not None, f"Cannot read source archive file: {name}")
            if content is not None:
                with content:
                    require(
                        content.read() == (root / "src" / name).read_bytes(),
                        f"Source archive differs from current package: {name}",
                    )
        for member in archive.getmembers():
            parts = Path(member.name).parts
            require(
                not {
                    ".env",
                    ".uv-cache",
                    ".venv",
                    "reports",
                    "config.db",
                    "secret.key",
                    "Load Contacts.csv",
                }.intersection(parts),
                "Private data entered the source archive.",
            )
            require(
                not member.name.endswith((".db", ".key", ".sqlite3", ".pyc")),
                "Runtime state entered the archive.",
            )
    print("Wheel package contents, source equality, and source archive privacy checks passed.")


if __name__ == "__main__":
    main()
