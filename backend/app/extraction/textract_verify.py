"""Optional Amazon Textract cross-check for the Government Warning.

A second, independent witness for the one field with zero leeway. Unlike a vision LLM,
Textract transcribes literal pixels — it does not canonicalize casing or wording toward
the statutory form (the exact failure mode behind the 2026-07-06 regression) — and its
word bounding boxes give a *deterministic* prominence measure.

Enabled with WARNING_CROSSCHECK=on plus AWS credentials in the environment. If boto3,
credentials, or the service are unavailable, every function degrades to a no-op
(returns None) so the primary flow is never broken.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import Optional

from ..config import settings
from ..extraction.base import LabelExtraction
from ..rules import GOVERNMENT_WARNING_TEXT

_CANON = re.sub(r"\s+", " ", GOVERNMENT_WARNING_TEXT).strip()


@dataclass
class WarningWitness:
    """What Textract literally read for the warning (no normalization applied)."""

    found: bool
    literal_heading: Optional[str] = None      # e.g. "Government Warning:"
    heading_all_caps: Optional[bool] = None
    literal_text: Optional[str] = None
    differs_from_standard: Optional[bool] = None
    height_ratio: Optional[float] = None        # warning height / label median height
    prominence: Optional[str] = None            # "small" | "prominent" | None


def get_textract_client():
    """Return a Textract client, or None if disabled/unavailable (never raises)."""
    if not settings.WARNING_CROSSCHECK:
        return None
    try:
        import boto3

        return boto3.client("textract", region_name=settings.AWS_REGION or None)
    except Exception:
        return None


def crosscheck_warning(image_bytes: bytes) -> Optional[WarningWitness]:
    """Run Textract on the image and read the warning verbatim. None if unavailable."""
    client = get_textract_client()
    if client is None:
        return None
    try:
        resp = client.detect_document_text(Document={"Bytes": image_bytes})
    except Exception:
        return None
    return witness_from_blocks(resp.get("Blocks", []))


def witness_from_blocks(blocks: list[dict]) -> WarningWitness:
    """Build a WarningWitness from Textract DetectDocumentText blocks."""
    lines = [b.get("Text", "") for b in blocks if b.get("BlockType") == "LINE"]
    words = [
        (b.get("Text", ""), b.get("Geometry", {}).get("BoundingBox", {}).get("Height", 0.0))
        for b in blocks
        if b.get("BlockType") == "WORD"
    ]
    full = "\n".join(lines)

    m = re.search(r"government\s+warning", full, re.IGNORECASE)
    if not m:
        return WarningWitness(found=False)

    literal_text = full[m.start():].strip()
    colon = literal_text.find(":")
    literal_heading = literal_text[: colon + 1] if colon != -1 else literal_text[:19]

    letters = [c for c in literal_heading if c.isalpha()]
    heading_all_caps = bool(letters) and all(c.isupper() for c in letters)

    norm = re.sub(r"\s+", " ", literal_text).strip()
    differs = norm.lower() != _CANON.lower()

    height_ratio, prominence = _prominence(words)

    return WarningWitness(
        found=True,
        literal_heading=literal_heading.strip(),
        heading_all_caps=heading_all_caps,
        literal_text=norm,
        differs_from_standard=differs,
        height_ratio=height_ratio,
        prominence=prominence,
    )


def _prominence(words: list[tuple[str, float]]) -> tuple[Optional[float], Optional[str]]:
    """Median warning-word height vs the *non-warning* text height.

    The baseline is the rest of the label (brand, class, ABV, producer…), not all words
    — the warning is itself many words, so including it would bias the median toward the
    warning's own size and hide a genuinely tiny warning.
    """
    gi = next((i for i, (t, _) in enumerate(words) if t.lower() == "government"), None)
    if gi is None:
        return None, None
    other_heights = [h for _, h in words[:gi] if h > 0]
    warn_heights = [h for _, h in words[gi:] if h > 0]
    if not other_heights or not warn_heights:
        return None, None
    ratio = statistics.median(warn_heights) / statistics.median(other_heights)
    prominence = "small" if ratio < settings.CROSSCHECK_MIN_HEIGHT_RATIO else "prominent"
    return round(ratio, 3), prominence


def merge_witness(
    extraction: LabelExtraction, witness: Optional[WarningWitness]
) -> tuple[LabelExtraction, Optional[str]]:
    """Fold the Textract witness into the extraction's warning signals, fail-closed.

    A casing/wording problem seen by *either* source is treated as present, so a model
    that laundered the transcription can't hide a violation the OCR caught. Returns the
    (possibly mutated) extraction and an optional note describing any disagreement.
    """
    if witness is None or not witness.found:
        return extraction, None

    notes: list[str] = []

    # Casing — fail-closed: if Textract says not-all-caps, it wins over the LLM.
    if witness.heading_all_caps is False:
        if extraction.warning_heading_all_caps is not False:
            notes.append(
                f"Textract read the heading as {witness.literal_heading!r} (not all caps)"
            )
        extraction.warning_heading_all_caps = False

    # Wording — fail-closed on any deviation Textract saw.
    if witness.differs_from_standard:
        if not extraction.warning_differs_from_standard:
            notes.append("Textract read the warning wording as differing from the statutory text")
        extraction.warning_differs_from_standard = True

    # Prominence — deterministic geometry augments the LLM's guess (only ever a warn).
    if witness.prominence == "small" and extraction.warning_prominence not in ("small", "buried"):
        extraction.warning_prominence = "small"
        notes.append(
            f"Textract measured the warning at {int((witness.height_ratio or 0) * 100)}% "
            "of the label's typical text height"
        )

    note = ("Cross-check: " + "; ".join(notes) + ".") if notes else None
    return extraction, note
