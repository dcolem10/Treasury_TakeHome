"""Extraction interface.

Any OCR/vision implementation (cloud LLM, local Tesseract, future on-prem model) implements
`ExtractionBackend`. The rest of the app depends only on this contract, so swapping the
backend for the air-gapped production network is a config change, not a rewrite.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LabelExtraction:
    """Raw text/fields read off a label image. No compliance judgment here.

    Beyond the text fields, the backend may report visual signals it observed:
    whether the warning appears bold, how prominent the warning looks, and an
    overall image-quality read. These feed prominence and messy-photo handling.
    """

    readable: bool
    fields: dict[str, Optional[str]] = field(default_factory=dict)
    raw_text: str = ""
    error: Optional[str] = None
    # Visual signals (None when the backend can't judge them, e.g. local OCR).
    warning_is_bold: Optional[bool] = None
    warning_prominence: Optional[str] = None  # "prominent" | "small" | "buried"
    image_quality: Optional[str] = None  # "clear" | "marginal" | "unreadable"
    # Capitalization-fidelity signals for the warning heading. Some models
    # "helpfully" canonicalize the transcription toward the statutory ALL-CAPS
    # form, which would launder a title-case heading past the strict caps check
    # — so the heading's casing is also captured as targeted observations.
    warning_heading_exact: Optional[str] = None
    warning_heading_all_caps: Optional[bool] = None
    # Body-fidelity signal: model's explicit report of whether the printed warning
    # deviates from the statutory text (defends the exact-match the same way the
    # heading signals defend the caps check).
    warning_differs_from_standard: Optional[bool] = None
    warning_deviation_note: Optional[str] = None

    def get(self, key: str) -> Optional[str]:
        value = self.fields.get(key)
        if value is None:
            return None
        value = value.strip()
        return value or None


class ExtractionBackend(ABC):
    """Reads structured label fields from raw image bytes."""

    name: str = "base"

    @abstractmethod
    def extract(self, image_bytes: bytes, content_type: str) -> LabelExtraction:
        """Return a LabelExtraction. Must not raise for unreadable images —
        set ``readable=False`` and an ``error`` message instead."""
        raise NotImplementedError
