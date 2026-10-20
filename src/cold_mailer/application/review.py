"""Deterministic authoring hints; no delivery or factual correctness guarantees."""

import re
import textwrap


def quality_hints(subject: str, body: str) -> list[str]:
    hints = []
    if not subject.strip():
        hints.append("Add a subject before approval.")
    if len(subject) > 78:
        hints.append("Long subject: many inboxes will truncate it.")
    if len(body.split()) > 250:
        hints.append("Over 250 words: consider a shorter message.")
    if re.search(r"\S{80,}", body):
        hints.append("Long unbroken text may be difficult to read on narrow screens.")
    if "{{" in body or "}}" in body:
        hints.append("Unresolved template variables need review.")
    if re.search(r"\b(guarantee[ds]?|100%|risk.free)\b", body, re.IGNORECASE):
        hints.append(
            "Review strong claims against your supplied facts; this check cannot verify them."
        )
    return hints


def reading_preview(subject: str, body: str, width: int = 45) -> str:
    return (
        "Subject: "
        + subject
        + "\n\n"
        + "\n".join(
            textwrap.fill(line, width=width, replace_whitespace=False) if line else ""
            for line in body.splitlines()
        )
    )
