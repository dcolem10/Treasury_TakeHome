"""Strict Government Warning validation (the highest-stakes check)."""
from app.comparison.warning import validate_warning
from app.rules import GOVERNMENT_WARNING_TEXT


def test_exact_warning_passes():
    assert validate_warning(GOVERNMENT_WARNING_TEXT).status == "pass"


def test_warning_with_extra_whitespace_and_newlines_passes():
    noisy = GOVERNMENT_WARNING_TEXT.replace(" ", "  ").replace("(2)", "\n(2)")
    assert validate_warning(noisy).status == "pass"


def test_title_case_prefix_fails():
    bad = GOVERNMENT_WARNING_TEXT.replace("GOVERNMENT WARNING:", "Government Warning:")
    result = validate_warning(bad)
    assert result.status == "fail"
    assert "capital" in result.reason.lower()


def test_missing_warning_fails():
    result = validate_warning(None)
    assert result.status == "fail"
    assert "not found" in result.reason.lower()


def test_reworded_warning_fails():
    bad = "GOVERNMENT WARNING: Drinking is bad for you and may cause problems."
    assert validate_warning(bad).status == "fail"


def test_missing_prefix_fails():
    body = GOVERNMENT_WARNING_TEXT.replace("GOVERNMENT WARNING: ", "")
    assert validate_warning(body).status == "fail"
