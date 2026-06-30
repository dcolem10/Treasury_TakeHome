"""Local OCR extraction backend (air-gapped production path).

This is a documented stub for the firewall-restricted production network, where cloud-ML
endpoints are blocked. It runs Tesseract locally to recover raw text, then does light
heuristic field-spotting. It is intentionally simpler than the Claude backend: it exists to
prove the interface is swappable, not to match the cloud backend's accuracy.

Requires the system `tesseract` binary and `pytesseract` (not in requirements by default).
"""
from __future__ import annotations

import io
import re
from typing import Optional

from ..rules import EXTRACTION_FIELDS, WARNING_PREFIX
from .base import ExtractionBackend, LabelExtraction


class TesseractBackend(ExtractionBackend):
    name = "tesseract"

    def extract(self, image_bytes: bytes, content_type: str) -> LabelExtraction:
        try:
            import pytesseract
            from PIL import Image
        except Exception as exc:
            return LabelExtraction(
                readable=False,
                error=(
                    "Local OCR backend unavailable (pytesseract/Pillow or the tesseract "
                    f"binary is not installed): {exc}"
                ),
            )

        try:
            image = Image.open(io.BytesIO(image_bytes))
            raw_text = pytesseract.image_to_string(image)
        except Exception as exc:
            return LabelExtraction(readable=False, error=f"Local OCR failed: {exc}")

        text = raw_text.strip()
        if len(text) < 8:
            return LabelExtraction(
                readable=False,
                raw_text=text,
                error="Label text could not be read clearly.",
            )

        return LabelExtraction(
            readable=True,
            fields=_heuristic_fields(raw_text),
            raw_text=text,
        )


def _heuristic_fields(raw_text: str) -> dict[str, Optional[str]]:
    """Best-effort field spotting from flat OCR text. Cloud backend is preferred.

    TTB labels follow a stable top-to-bottom layout (brand, class/type, then the
    ABV / net-contents / producer block, then the warning). We use that ordering
    plus keyword anchors to recover the structured fields from flat OCR text.
    """
    fields: dict[str, Optional[str]] = {key: None for key in EXTRACTION_FIELDS}

    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

    # Government warning: capture from the prefix to the end of the statement.
    idx = raw_text.upper().find(WARNING_PREFIX)
    if idx != -1:
        fields["government_warning"] = " ".join(raw_text[idx:].split())

    # Index of the warning line, used as a lower bound for the header/producer block.
    warn_line = next(
        (i for i, ln in enumerate(lines) if ln.upper().startswith(WARNING_PREFIX)),
        len(lines),
    )

    abv = re.search(r"\d{1,2}(?:\.\d+)?\s*%\s*(?:alc|abv)?[^\n]*", raw_text, re.IGNORECASE)
    if abv:
        fields["alcohol_content"] = abv.group(0).strip()

    net = re.search(r"\d+(?:\.\d+)?\s*(?:ml|l|fl\.?\s*oz|liters?)\b", raw_text, re.IGNORECASE)
    if net:
        fields["net_contents"] = net.group(0).strip()

    # Brand name and class/type: the first two non-empty text lines, by layout
    # convention (brand is the largest line, class/type sits directly beneath).
    def _is_fieldish(ln: str) -> bool:
        low = ln.lower()
        return bool(
            ln.upper().startswith(WARNING_PREFIX)
            or re.search(r"\d{1,2}(?:\.\d+)?\s*%", ln)
            or re.search(r"\d+(?:\.\d+)?\s*(?:ml|l|fl\.?\s*oz|liters?)\b", low)
            or low.startswith(("bottled", "distilled", "imported", "produced"))
        )

    header = [ln for ln in lines[:warn_line] if not _is_fieldish(ln)]
    if header:
        fields["brand_name"] = header[0]
    if len(header) > 1:
        fields["class_type"] = header[1]

    # Producer / bottler: the block beginning at a producer keyword and running
    # up to the warning (may wrap across OCR lines, e.g. a city/state on its own).
    prod_start = next(
        (
            i
            for i, ln in enumerate(lines[:warn_line])
            if ln.lower().startswith(("bottled", "distilled", "imported", "produced"))
        ),
        None,
    )
    if prod_start is not None:
        producer = " ".join(lines[prod_start:warn_line]).strip().rstrip(",")
        fields["producer"] = producer or None

    return fields
