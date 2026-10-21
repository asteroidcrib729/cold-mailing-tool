"""Apply the plan's aggregate and critical-service coverage gates without hiding failures."""

import json
from pathlib import Path

CRITICAL = (
    "src/cold_mailer/domain/models.py",
    "src/cold_mailer/application/campaigns.py",
    "src/cold_mailer/infrastructure/storage.py",
    "src/cold_mailer/infrastructure/smtp.py",
    "src/cold_mailer/infrastructure/oauth_accounts.py",
    "src/cold_mailer/infrastructure/oauth_browser.py",
    "src/cold_mailer/infrastructure/oauth_mail.py",
    "src/cold_mailer/infrastructure/oauth_secrets.py",
)


def main() -> int:
    report = json.loads(Path("reports/coverage.json").read_text(encoding="utf-8"))
    failures = []
    files = {name.replace("\\", "/"): data for name, data in report["files"].items()}
    if report["totals"]["percent_covered"] < 90:
        failures.append("Overall coverage is below 90%.")
    for name in CRITICAL:
        summary = files.get(name, {}).get("summary")
        if summary is None or summary["percent_covered"] < 95:
            failures.append(f"Critical module {name} is below 95%.")
    print("\n".join(failures) or "Coverage gates passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
