"""Builds a Verdict from a LabelExtraction, in both verification modes.

All pass/fail logic is here (deterministic, unit-tested) — the extraction backend only
supplies the text. See docs/RULES.md for the matching strategy per field.
"""
from __future__ import annotations

from ..config import settings
from ..extraction.base import LabelExtraction
from ..rules import FIELD_LABELS, REQUIRED_FIELDS
from ..schemas import CheckResult, ExtractedFields, Verdict
from . import fuzzy
from .warning import validate_warning

# Free-text fields compared by fuzzy similarity in compare mode.
_FUZZY_FIELDS = ["brand_name", "class_type", "producer"]
# Fields compared by normalized exact match.
_EXACT_FIELDS = ["net_contents", "country_of_origin"]


def _extracted_model(extraction: LabelExtraction) -> ExtractedFields:
    return ExtractedFields(**{k: extraction.get(k) for k in ExtractedFields.model_fields})


def _overall(checks: list[CheckResult]) -> str:
    return "fail" if any(c.status == "fail" for c in checks) else "pass"


def compare_to_fields(
    extraction: LabelExtraction, expected: dict[str, str | None]
) -> list[CheckResult]:
    """Compare the label against agent-supplied expected values."""
    checks: list[CheckResult] = []

    for field in _FUZZY_FIELDS:
        exp = (expected.get(field) or "").strip()
        if not exp:
            continue  # agent left it blank -> not checked
        found = extraction.get(field)
        score = fuzzy.similarity(exp, found)
        if score >= settings.FUZZY_PASS:
            status, reason = "pass", f"Matches (similarity {score})."
        elif score >= settings.FUZZY_WARN:
            status, reason = "warn", f"Near match (similarity {score}); please verify by eye."
        else:
            status, reason = "fail", f"Does not match the application (similarity {score})."
        checks.append(_row(field, status, reason, expected=exp, found=found))

    for field in _EXACT_FIELDS:
        exp = (expected.get(field) or "").strip()
        if not exp:
            continue
        found = extraction.get(field)
        if fuzzy.normalized_equal(exp, found):
            checks.append(_row(field, "pass", "Matches the application.", exp, found))
        else:
            checks.append(
                _row(field, "fail", "Does not match the application.", exp, found)
            )

    # Alcohol content: compare the numeric ABV figure.
    exp_abv = (expected.get("alcohol_content") or "").strip()
    if exp_abv:
        found = extraction.get("alcohol_content")
        a, b = fuzzy.extract_abv(exp_abv), fuzzy.extract_abv(found)
        if b is None:
            checks.append(
                _row("alcohol_content", "fail", "No alcohol content found on the label.",
                     exp_abv, found)
            )
        elif a is not None and abs(a - b) < 0.05:
            checks.append(
                _row("alcohol_content", "pass", f"ABV matches ({b:g}%).", exp_abv, found)
            )
        else:
            checks.append(
                _row("alcohol_content", "fail",
                     f"ABV differs (application {a:g}% vs label {b:g}%).", exp_abv, found)
            )

    # Government warning is always validated strictly, regardless of expected input.
    checks.append(_warning_check(extraction))
    return checks


def rule_check(extraction: LabelExtraction) -> list[CheckResult]:
    """Validate TTB compliance from the label alone (no expected values)."""
    checks: list[CheckResult] = []

    for field in REQUIRED_FIELDS:
        if field == "government_warning":
            continue  # handled below with strict validation
        found = extraction.get(field)
        if field == "alcohol_content":
            if found and fuzzy.looks_like_abv(found):
                checks.append(_row(field, "pass", f"Present: {found}", found=found))
            elif found:
                checks.append(
                    _row(field, "warn", f"Found '{found}' but no clear ABV figure.", found=found)
                )
            else:
                checks.append(_row(field, "fail", "Alcohol content is missing."))
            continue
        if found:
            checks.append(_row(field, "pass", "Present on the label.", found=found))
        else:
            checks.append(_row(field, "fail", f"{FIELD_LABELS[field]} is missing."))

    # Country of origin is conditional (imports only) -> warn when absent.
    coo = extraction.get("country_of_origin")
    if coo:
        checks.append(_row("country_of_origin", "pass", "Present on the label.", found=coo))
    else:
        checks.append(
            _row("country_of_origin", "warn",
                 "Not found — required only for imported products.")
        )

    checks.append(_warning_check(extraction))
    return checks


def build_verdict(
    extraction: LabelExtraction, mode: str, expected: dict[str, str | None] | None = None
) -> Verdict:
    """Top-level entry: produce a full Verdict, handling unreadable images."""
    if not extraction.readable:
        return Verdict(
            overall="unreadable",
            readable=False,
            mode=mode,  # type: ignore[arg-type]
            extracted=_extracted_model(extraction),
            error=extraction.error or "The label image could not be read. Please resubmit a clearer photo.",
        )

    if mode == "compare":
        checks = compare_to_fields(extraction, expected or {})
    else:
        checks = rule_check(extraction)

    return Verdict(
        overall=_overall(checks),  # type: ignore[arg-type]
        readable=True,
        mode=mode,  # type: ignore[arg-type]
        checks=checks,
        extracted=_extracted_model(extraction),
    )


def _warning_check(extraction: LabelExtraction) -> CheckResult:
    found = extraction.get("government_warning")
    result = validate_warning(found)
    return _row("government_warning", result.status, result.reason, found=found)


def _row(
    field: str,
    status: str,
    reason: str,
    expected: str | None = None,
    found: str | None = None,
) -> CheckResult:
    return CheckResult(
        field=field,
        label=FIELD_LABELS.get(field, field),
        status=status,  # type: ignore[arg-type]
        expected=expected,
        found=found,
        reason=reason,
    )
