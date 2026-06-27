"""Selects the extraction backend from configuration (cached as a singleton)."""
from __future__ import annotations

from functools import lru_cache

from ..config import settings
from .base import ExtractionBackend


@lru_cache(maxsize=None)
def get_backend() -> ExtractionBackend:
    choice = settings.EXTRACTION_BACKEND.lower()
    if choice == "tesseract":
        from .tesseract_backend import TesseractBackend

        return TesseractBackend()
    if choice == "claude":
        from .claude_backend import ClaudeVisionBackend

        return ClaudeVisionBackend()
    raise ValueError(f"Unknown EXTRACTION_BACKEND: {settings.EXTRACTION_BACKEND!r}")
