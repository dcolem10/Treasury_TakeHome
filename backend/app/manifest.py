"""Parse an application manifest CSV for batch compare mode.

An agent processing a big import can upload one CSV describing what each label's
application *says*. Each row is matched to an uploaded image by filename, and that image is
then verified in compare mode against the row's expected values.

Expected columns (header row, case-insensitive; extra columns ignored):
  filename, brand_name, class_type, alcohol_content, net_contents, producer, country_of_origin

Only `filename` is required. Any expected column left blank for a row is simply not checked.
"""
from __future__ import annotations

import csv
import io

from .rules import EXTRACTION_FIELDS

# Columns an agent may supply (everything except the warning, which is always strict).
MANIFEST_FIELDS = [f for f in EXTRACTION_FIELDS if f != "government_warning"]

# Accept a few friendly header aliases.
_ALIASES = {
    "file": "filename",
    "file_name": "filename",
    "image": "filename",
    "brand": "brand_name",
    "class": "class_type",
    "type": "class_type",
    "class/type": "class_type",
    "abv": "alcohol_content",
    "alcohol": "alcohol_content",
    "alcohol_content": "alcohol_content",
    "net": "net_contents",
    "net_contents": "net_contents",
    "bottler": "producer",
    "producer": "producer",
    "origin": "country_of_origin",
    "country": "country_of_origin",
    "country_of_origin": "country_of_origin",
}


def _canon(header: str) -> str:
    key = header.strip().lower().replace(" ", "_")
    return _ALIASES.get(key, key)


def parse_manifest(data: bytes) -> dict[str, dict[str, str]]:
    """Return {normalized_filename: {field: expected_value}}.

    Filenames are matched case-insensitively and without surrounding whitespace.
    Raises ValueError if the CSV has no usable `filename` column.
    """
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError("The manifest CSV is empty.")

    headers = [_canon(h) for h in rows[0]]
    if "filename" not in headers:
        raise ValueError("The manifest CSV must have a 'filename' column.")

    out: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        record = dict(zip(headers, (c.strip() for c in row)))
        name = (record.get("filename") or "").strip()
        if not name:
            continue
        expected = {f: record[f] for f in MANIFEST_FIELDS if record.get(f)}
        out[name.lower()] = expected
    return out


def match_expected(
    manifest: dict[str, dict[str, str]], filename: str
) -> dict[str, str] | None:
    """Look up a file's expected values, tolerant of case and path prefixes."""
    if not manifest:
        return None
    name = (filename or "").strip().lower()
    if name in manifest:
        return manifest[name]
    base = name.rsplit("/", 1)[-1]
    return manifest.get(base)
