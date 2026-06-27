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
    """Raw text/fields read off a label image. No compliance judgment here."""

    readable: bool
    fields: dict[str, Optional[str]] = field(default_factory=dict)
    raw_text: str = ""
    error: Optional[str] = None

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
