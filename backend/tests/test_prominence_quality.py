"""Warning prominence + messy-photo (quality) handling.

These cover the deterministic logic. The upstream visual *signals* come from the vision
model and must be confirmed on the live deployment (see docs/TASKS.md).
"""
from app.comparison.compare import build_verdict
from app.comparison.warning import validate_warning
from app.extraction.base import LabelExtraction
from app.rules import GOVERNMENT_WARNING_TEXT


def _extraction(**kw) -> LabelExtraction:
    fields = {
        "brand_name": "Old Tom Distillery",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "producer": "Old Tom Distillery, KY",
        "country_of_origin": None,
        "government_warning": GOVERNMENT_WARNING_TEXT,
    }
    return LabelExtraction(readable=True, fields=fields, **kw)


# ---- warning prominence ----
def test_exact_warning_still_passes_when_prominent_and_bold():
    assert validate_warning(GOVERNMENT_WARNING_TEXT, is_bold=True, prominence="prominent").status == "pass"


def test_non_bold_warning_warns_not_fails():
    r = validate_warning(GOVERNMENT_WARNING_TEXT, is_bold=False, prominence="prominent")
    assert r.status == "warn" and "bold" in r.reason.lower()


def test_buried_warning_warns():
    r = validate_warning(GOVERNMENT_WARNING_TEXT, prominence="buried")
    assert r.status == "warn" and "buried" in r.reason.lower()


def test_wrong_text_still_fails_regardless_of_prominence():
    bad = GOVERNMENT_WARNING_TEXT.replace("GOVERNMENT WARNING:", "Government Warning:")
    assert validate_warning(bad, is_bold=True, prominence="prominent").status == "fail"


def test_prominence_warn_makes_overall_pass_not_fail():
    # A warn on the warning should not fail the whole label.
    v = build_verdict(_extraction(warning_is_bold=False), "rules")
    warning = next(c for c in v.checks if c.field == "government_warning")
    assert warning.status == "warn"
    assert v.overall == "pass"


# ---- messy photo / quality ----
def test_marginal_quality_sets_note_but_still_evaluates():
    v = build_verdict(_extraction(image_quality="marginal"), "rules")
    assert v.overall == "pass"
    assert v.quality_note and "low quality" in v.quality_note.lower()


def test_clear_quality_has_no_note():
    v = build_verdict(_extraction(image_quality="clear"), "rules")
    assert v.quality_note is None


def test_unreadable_flag_short_circuits():
    v = build_verdict(LabelExtraction(readable=False, error="too dark"), "rules")
    assert v.overall == "unreadable"
