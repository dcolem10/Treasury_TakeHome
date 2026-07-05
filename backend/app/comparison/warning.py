"""Strict validation of the Government Warning statement.

The warning is the one field that is never fuzzy-matched: TTB requires it verbatim, with
"GOVERNMENT WARNING:" in all capital letters (and bold). We validate caps + exact wording
from the transcribed text. See docs/RULES.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..rules import GOVERNMENT_WARNING_TEXT, WARNING_PREFIX

# Canonical text with whitespace collapsed, for body comparison.
_CANONICAL = re.sub(r"\s+", " ", GOVERNMENT_WARNING_TEXT).strip()


@dataclass
class WarningResult:
    status: str  # "pass" | "fail" | "warn"
    reason: str


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_warning(
    found: str | None,
    is_bold: bool | None = None,
    prominence: str | None = None,
) -> WarningResult:
    """Judge a transcribed warning string against the statutory requirement.

    `is_bold` / `prominence` are optional visual signals from the extraction backend.
    Text/caps errors are hard fails. When the text is correct but the warning looks
    non-bold, shrunk, or buried, we return a **warn** — TTB requires bold + a minimum
    type size, but these visual reads are heuristic, so we flag for the agent's eye
    rather than auto-rejecting. See docs/RULES.md.
    """
    if not found or not found.strip():
        return WarningResult("fail", "Government Warning statement not found on the label.")

    collapsed = _collapse(found)

    # 1) The prefix must be present and in ALL CAPS.
    if WARNING_PREFIX not in collapsed:
        # Is it there but mis-cased?
        if WARNING_PREFIX.lower() in collapsed.lower():
            return WarningResult(
                "fail",
                "'GOVERNMENT WARNING:' must be in all capital letters.",
            )
        return WarningResult(
            "fail", "The required 'GOVERNMENT WARNING:' heading is missing."
        )

    # 2) The full body must match the canonical statement exactly (after whitespace collapse).
    if collapsed != _CANONICAL:
        if collapsed.lower() == _CANONICAL.lower():
            return WarningResult(
                "fail",
                "Warning wording matches but capitalization differs from the required text.",
            )
        return WarningResult(
            "fail",
            "Warning text does not match the required statement word-for-word.",
        )

    # 3) Text is exact. Now flag prominence problems (bold / size / burying).
    issues = []
    if prominence in ("small", "buried"):
        issues.append(
            "the warning looks smaller or less prominent than required"
            if prominence == "small"
            else "the warning appears buried in other text"
        )
    if is_bold is False:
        issues.append("'GOVERNMENT WARNING:' does not appear bold")
    if issues:
        return WarningResult(
            "warn",
            "Warning text is correct, but " + "; ".join(issues) + " — please verify by eye.",
        )

    return WarningResult("pass", "Government Warning matches the required statement exactly.")
