"""Check package boundaries, plan links, and safe source without reading secrets."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "cold_mailer"
LEGACY_MODULES = {
    "app_ui",
    "main_headless",
    "bootstrap",
    "config",
    "domain",
    "ports",
    "campaign_service",
    "persistence",
    "credentials",
    "ai_generator",
    "mail_sender",
    "data_loader",
    "templating",
    "utils",
    "db",
    "ui_models",
    "ui_workers",
}


def main() -> int:
    errors: list[str] = []
    for path in ROOT.glob("*.py"):
        errors.append(f"{path.name}: application Python source belongs under src/cold_mailer")
    for package in ("", "domain", "application", "infrastructure", "ui"):
        if not (SOURCE / package / "__init__.py").is_file():
            errors.append(f"Missing package initializer: cold_mailer/{package}")
    for path in [*SOURCE.rglob("*.py"), *(ROOT / "tests").rglob("*.py")]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for module in modules:
                if module.split(".")[0] in LEGACY_MODULES:
                    errors.append(f"{path.relative_to(ROOT)}: obsolete top-level import {module}")
                if path.parent == SOURCE / "domain" and (
                    module.startswith(("PySide6", "google", "sqlite3", "keyring"))
                    or (
                        module.startswith("cold_mailer.")
                        and not module.startswith("cold_mailer.domain")
                    )
                ):
                    errors.append(f"{path.relative_to(ROOT)}: domain boundary imports {module}")
    for path in [ROOT / "README.md", *sorted((ROOT / "development-plans").glob("*.md"))]:
        content = path.read_text(encoding="utf-8")
        if content.count("```") % 2:
            errors.append(f"{path.name}: unclosed code fence")
        headings = {
            re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
            for heading in re.findall(r"^#{1,6}\s+(.+)$", content, flags=re.MULTILINE)
        }
        for link in re.findall(r"\]\(([^)]+)\)", content):
            if link.startswith("#") and link[1:] not in headings:
                errors.append(f"{path.name}: missing local anchor {link}")
            if (
                not link.startswith(("https://", "http://", "#"))
                and not (path.parent / link).exists()
            ):
                errors.append(f"{path.name}: missing local link {link}")
    for path in [
        *SOURCE.rglob("*.py"),
        *ROOT.glob("*.toml"),
        *ROOT.glob(".github/workflows/*.yml"),
    ]:
        if re.search(r"AIza[0-9A-Za-z_-]{25,}", path.read_text(encoding="utf-8")):
            errors.append(f"{path.name}: potential API key literal (redacted)")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        "Repository boundaries and documentation links passed. This is not a full history secret scan."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
