"""Runtime configuration, sourced from environment variables."""
from __future__ import annotations

import os


class Settings:
    """Process-wide settings. Read once at import time."""

    # Which extraction backend to use: "claude" (prototype) or "tesseract" (local/air-gapped).
    EXTRACTION_BACKEND: str = os.getenv("EXTRACTION_BACKEND", "claude")

    # Anthropic config (used by the Claude vision backend).
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    # Per-image extraction timeout (seconds) — protects the 5s budget.
    EXTRACTION_TIMEOUT_S: float = float(os.getenv("EXTRACTION_TIMEOUT_S", "30"))

    # Max concurrent extractions in a batch request.
    BATCH_CONCURRENCY: int = int(os.getenv("BATCH_CONCURRENCY", "8"))

    # Fuzzy thresholds (see docs/RULES.md).
    FUZZY_PASS: int = int(os.getenv("FUZZY_PASS", "88"))
    FUZZY_WARN: int = int(os.getenv("FUZZY_WARN", "80"))


settings = Settings()
