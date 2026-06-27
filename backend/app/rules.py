"""TTB rules: the canonical Government Warning and required-field definitions.

See docs/RULES.md for the authoritative spec and sources (27 CFR Part 16).
"""
from __future__ import annotations

# The mandatory health warning, verbatim from 27 CFR Part 16, Subpart B (16.21).
# The "GOVERNMENT WARNING:" prefix must appear in all capital letters and bold.
GOVERNMENT_WARNING_TEXT = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

# The literal prefix that must be in ALL CAPS.
WARNING_PREFIX = "GOVERNMENT WARNING:"

# Fields the app knows how to read off a label.
EXTRACTION_FIELDS = [
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "producer",
    "country_of_origin",
    "government_warning",
]

# Human-friendly labels for the UI / check rows.
FIELD_LABELS = {
    "brand_name": "Brand Name",
    "class_type": "Class / Type",
    "alcohol_content": "Alcohol Content",
    "net_contents": "Net Contents",
    "producer": "Producer / Bottler",
    "country_of_origin": "Country of Origin",
    "government_warning": "Government Warning",
}

# Fields that are mandatory in rule-check mode and hard-fail when missing.
# country_of_origin is conditional (imports only) -> warn, not fail (see docs/RULES.md).
REQUIRED_FIELDS = [
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "producer",
    "government_warning",
]
