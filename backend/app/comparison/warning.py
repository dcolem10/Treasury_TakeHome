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


def validate_warning(found: str | None) -> WarningResult:
    """Judge a transcribed warning string against the statutory requirement."""
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
    if collapsed == _CANONICAL:
        return WarningResult("pass", "Government Warning matches the required statement exactly.")

    # Distinguish "right words, minor OCR noise" from "wrong text" using a case-insensitive
    # compare of the remainder — but any real difference is still a fail (strict field).
    if collapsed.lower() == _CANONICAL.lower():
        return WarningResult(
            "fail",
            "Warning wording matches but capitalization differs from the required text.",
        )

    return WarningResult(
        "fail",
        "Warning text does not match the required statement word-for-word.",
    )
