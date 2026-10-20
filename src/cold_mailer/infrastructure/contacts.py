"""Bounded CSV/XLSX import with row diagnostics and stable string values."""

from __future__ import annotations

import csv
import zipfile
from collections.abc import Iterable
from pathlib import Path

from cold_mailer.domain.models import ImportIssue, ImportReport, ValidationError, address

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000


def load_contacts(path: Path, suppressed: set[str] | None = None) -> ImportReport:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValidationError("Choose a CSV/XLSX file no larger than 10 MiB.")
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            try:
                return parse_rows(csv.reader(stream), suppressed)
            except UnicodeError, csv.Error:
                raise ValidationError("CSV must be valid UTF-8 with a header row.") from None
    if path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook

        try:
            with zipfile.ZipFile(path) as archive:
                if sum(item.file_size for item in archive.infolist()) > 50 * MAX_BYTES:
                    raise ValidationError("The expanded workbook exceeds the size limit.")
            workbook = load_workbook(path, read_only=True, data_only=False, keep_links=False)
            try:
                sheet = workbook.active
                if sheet is None:
                    raise ValidationError("The workbook contains no active sheet.")
                return parse_rows(sheet.values, suppressed)
            finally:
                workbook.close()
        except zipfile.BadZipFile, KeyError, ValueError:
            raise ValidationError("The workbook is invalid or unsupported.") from None
    raise ValidationError("Only CSV and XLSX are supported; convert legacy XLS files first.")


def parse_rows(
    rows: Iterable[Iterable[object]], suppressed: set[str] | None = None
) -> ImportReport:
    iterator = iter(rows)
    columns = [str(cell or "").strip().lower() for cell in next(iterator, [])]
    if not columns or "email" not in columns or len(columns) != len(set(columns)) or "" in columns:
        raise ValidationError("A unique, nonempty header row containing email is required.")
    if len(columns) > 100:
        raise ValidationError("At most 100 contact columns are supported.")
    report = ImportReport()
    seen: set[str] = set()
    for number, row in enumerate(iterator, 2):
        if number > MAX_ROWS + 1:
            raise ValidationError("At most 10,000 contact rows are supported.")
        values = [
            "" if cell is None else str(cell).replace("\r\n", "\n").replace("\r", "\n").strip()
            for cell in row
        ]
        if not any(values):
            continue
        if len(values) != len(columns) or any(len(cell) > 10_000 for cell in values):
            report.issues.append(ImportIssue(number, "Column count or field length is invalid."))
            continue
        contact = dict(zip(columns, values, strict=True))
        try:
            contact["email"] = address(contact["email"])
        except ValidationError as exc:
            report.issues.append(ImportIssue(number, str(exc)))
            continue
        key = contact["email"]
        if key in (suppressed or set()):
            report.suppressed += 1
        elif key in seen:
            report.duplicates += 1
        else:
            report.contacts.append(contact)
            seen.add(key)
    return report


class DataLoader:
    """Compatibility entry point for callers of the original loader."""

    @staticmethod
    def load_contacts(file_path: str) -> list[dict[str, str]]:
        return load_contacts(Path(file_path)).contacts
