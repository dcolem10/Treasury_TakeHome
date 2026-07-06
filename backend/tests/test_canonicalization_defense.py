"""Anti-canonicalization defense for the warning caps check.

Live regression (2026-07-06): switching extraction models caused a title-case
'Government Warning:' heading to be transcribed as canonical ALL CAPS, so the
transcription-only caps check false-PASSED sample 02. These tests pin the fix:
targeted heading-casing signals outrank the transcription.
"""
from app.comparison.compare import build_verdict
from app.comparison.warning import validate_warning
from app.extraction.base import LabelExtraction
from app.rules import GOVERNMENT_WARNING_TEXT


def test_live_regression_canonicalized_transcript_still_fails():
    # The model transcribed canonical ALL CAPS, but truthfully reports the
    # heading is not all caps -> must FAIL.
    r = validate_warning(GOVERNMENT_WARNING_TEXT, heading_all_caps=False)
    assert r.status == "fail"
    assert "capital" in r.reason.lower()


def test_heading_exact_with_lowercase_fails_despite_canonical_transcript():
    r = validate_warning(
        GOVERNMENT_WARNING_TEXT,
        heading_exact="Government Warning: (1)",
        heading_all_caps=True,  # even a lying/confused boolean doesn't save it
    )
    assert r.status == "fail"
    assert "Government Warning:" in r.reason


def test_truthful_all_caps_signals_still_pass():
    r = validate_warning(
        GOVERNMENT_WARNING_TEXT,
        heading_exact="GOVERNMENT WARNING: (1)",
        heading_all_caps=True,
    )
    assert r.status == "pass"


def test_body_deviation_signal_fails_despite_canonical_transcript():
    # Model canonicalized a misspelled printed warning into perfect statutory
    # text, but truthfully reports the deviation -> must FAIL.
    r = validate_warning(
        GOVERNMENT_WARNING_TEXT,
        heading_exact="GOVERNMENT WARNING: (1)",
        heading_all_caps=True,
        differs_from_standard=True,
        deviation_note="label prints 'birth defect' instead of 'birth defects'",
    )
    assert r.status == "fail"
    assert "birth defect" in r.reason


def test_body_deviation_false_does_not_block_pass():
    r = validate_warning(
        GOVERNMENT_WARNING_TEXT,
        heading_all_caps=True,
        differs_from_standard=False,
    )
    assert r.status == "pass"


def test_absent_signals_keep_prior_behavior():
    # Old deployments / tesseract backend send no signals: transcription rules.
    assert validate_warning(GOVERNMENT_WARNING_TEXT).status == "pass"
    bad = GOVERNMENT_WARNING_TEXT.replace("GOVERNMENT WARNING:", "Government Warning:")
    assert validate_warning(bad).status == "fail"


def test_end_to_end_verdict_fails_on_canonicalized_extraction():
    extraction = LabelExtraction(
        readable=True,
        fields={
            "brand_name": "Old Tom Distillery",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": "45% Alc./Vol. (90 Proof)",
            "net_contents": "750 mL",
            "producer": "Old Tom Distillery, KY",
            "country_of_origin": None,
            # Canonicalized by the model — the label actually printed title case.
            "government_warning": GOVERNMENT_WARNING_TEXT,
        },
        warning_heading_exact="Government Warning: (1)",
        warning_heading_all_caps=False,
    )
    v = build_verdict(extraction, "rules")
    warning = next(c for c in v.checks if c.field == "government_warning")
    assert warning.status == "fail"
    assert v.overall == "fail"
