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
    """Best-effort field spotting from flat OCR text. Cloud backend is preferred."""
    fields: dict[str, Optional[str]] = {key: None for key in EXTRACTION_FIELDS}

    # Government warning: capture from the prefix to the end of the statement.
    idx = raw_text.upper().find(WARNING_PREFIX)
    if idx != -1:
        fields["government_warning"] = " ".join(raw_text[idx:].split())

    abv = re.search(r"\d{1,2}(?:\.\d+)?\s*%\s*(?:alc|abv)?[^\n]*", raw_text, re.IGNORECASE)
    if abv:
        fields["alcohol_content"] = abv.group(0).strip()

    net = re.search(r"\d+(?:\.\d+)?\s*(?:ml|l|fl\.?\s*oz|liters?)\b", raw_text, re.IGNORECASE)
    if net:
        fields["net_contents"] = net.group(0).strip()

    return fields
