"""Fuzzy matching + compare/rule-check verdict logic."""
from app.comparison import fuzzy
from app.comparison.compare import build_verdict
from app.extraction.base import LabelExtraction
from app.rules import GOVERNMENT_WARNING_TEXT


def make_extraction(**fields) -> LabelExtraction:
    base = {
        "brand_name": "Old Tom Distillery",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "producer": "Old Tom Distillery, Bardstown, KY",
        "country_of_origin": None,
        "government_warning": GOVERNMENT_WARNING_TEXT,
    }
    base.update(fields)
    return LabelExtraction(readable=True, fields=base)


# ---- fuzzy ----
def test_fuzzy_forgives_case_and_punctuation():
    assert fuzzy.similarity("STONE'S THROW", "Stone's Throw") >= 88


def test_fuzzy_rejects_different_brands():
    assert fuzzy.similarity("Old Tom Distillery", "Pirate's Cove Rum") < 80


def test_extract_abv_from_proof():
    assert fuzzy.extract_abv("90 Proof") == 45.0


def test_producer_subset_forgives_bottler_boilerplate():
    # Regression: live smoke test 2026-07-05 — manifest producer failed at 75
    # against the label's "Distilled & Bottled by" phrasing.
    assert fuzzy.similarity_subset(
        "Old Tom Distillery, Bardstown, KY",
        "Distilled & Bottled by Old Tom Distillery, Bardstown, KY",
    ) >= 88


def test_producer_subset_still_fails_wrong_producer():
    assert fuzzy.similarity_subset(
        "Old Tom Distillery, Bardstown, KY",
        "Bottled by Pirate Cove Rum Co, Miami, FL",
    ) < 80


# ---- compare mode ----
def test_compare_manifest_row_for_sample_01_passes():
    """End-to-end regression for the live batch+manifest failure on 01_compliant.png."""
    v = build_verdict(
        make_extraction(producer="Distilled & Bottled by Old Tom Distillery, Bardstown, KY"),
        "compare",
        {
            "brand_name": "Old Tom Distillery",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": "45% Alc./Vol.",
            "net_contents": "750 mL",
            "producer": "Old Tom Distillery, Bardstown, KY",
        },
    )
    assert v.overall == "pass", [c for c in v.checks if c.status != "pass"]


def test_compare_brand_case_mismatch_passes():
    v = build_verdict(make_extraction(brand_name="STONE'S THROW"), "compare",
                      {"brand_name": "Stone's Throw"})
    brand = next(c for c in v.checks if c.field == "brand_name")
    assert brand.status == "pass"
    assert v.overall == "pass"


def test_compare_wrong_brand_fails():
    v = build_verdict(make_extraction(brand_name="Pirate's Cove Rum"), "compare",
                      {"brand_name": "Old Tom Distillery"})
    assert v.overall == "fail"


def test_compare_abv_mismatch_fails():
    v = build_verdict(make_extraction(), "compare", {"alcohol_content": "40% Alc./Vol."})
    abv = next(c for c in v.checks if c.field == "alcohol_content")
    assert abv.status == "fail"


def test_blank_expected_fields_are_skipped():
    v = build_verdict(make_extraction(), "compare", {"brand_name": ""})
    assert not any(c.field == "brand_name" for c in v.checks)


# ---- rule-check mode ----
def test_rules_complete_label_passes():
    v = build_verdict(make_extraction(), "rules")
    assert v.overall == "pass"


def test_rules_missing_required_field_fails():
    v = build_verdict(make_extraction(net_contents=None), "rules")
    nc = next(c for c in v.checks if c.field == "net_contents")
    assert nc.status == "fail"
    assert v.overall == "fail"


def test_rules_bad_warning_fails():
    bad = GOVERNMENT_WARNING_TEXT.replace("GOVERNMENT WARNING:", "Government Warning:")
    v = build_verdict(make_extraction(government_warning=bad), "rules")
    assert v.overall == "fail"


def test_country_of_origin_absent_is_warn_not_fail():
    v = build_verdict(make_extraction(country_of_origin=None), "rules")
    coo = next(c for c in v.checks if c.field == "country_of_origin")
    assert coo.status == "warn"


# ---- unreadable ----
def test_unreadable_image_short_circuits():
    v = build_verdict(LabelExtraction(readable=False, error="too blurry"), "rules")
    assert v.overall == "unreadable"
    assert v.readable is False
