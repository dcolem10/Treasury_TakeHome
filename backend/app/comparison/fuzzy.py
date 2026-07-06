"""Normalization + fuzzy similarity for free-text label fields.

Forgives the trivial differences a human agent would (case, punctuation, spacing,
accents) — e.g. "STONE'S THROW" vs "Stone's Throw" — while still catching real mismatches.
"""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz


def normalize(text: str | None) -> str:
    """Lowercase, strip accents, drop punctuation, collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def similarity(a: str | None, b: str | None) -> int:
    """0–100 token-sort similarity of two normalized strings."""
    na, nb = normalize(a), normalize(b)
    if not na and not nb:
        return 100
    if not na or not nb:
        return 0
    return int(round(fuzz.token_sort_ratio(na, nb)))


def similarity_subset(a: str | None, b: str | None) -> int:
    """0–100 subset-tolerant similarity (token_set_ratio).

    Used for the producer field, where the label legally wraps the name in
    boilerplate ("Distilled & Bottled by <name>") that the application omits.
    token_set_ratio ignores tokens unique to one side when the shared core
    matches, so the bottler prefix doesn't sink an obvious match — while a
    genuinely different producer still scores far below the fail threshold.
    Too lenient for brand/class (a subset brand is a real mismatch), so those
    stay on token_sort_ratio.
    """
    na, nb = normalize(a), normalize(b)
    if not na and not nb:
        return 100
    if not na or not nb:
        return 0
    return int(round(fuzz.token_set_ratio(na, nb)))


def normalized_equal(a: str | None, b: str | None) -> bool:
    """Exact match after normalization (units/case/spacing-insensitive)."""
    return normalize(a) == normalize(b) and normalize(a) != ""


def extract_abv(text: str | None) -> float | None:
    """Pull the ABV percentage figure from a string like '45% Alc./Vol. (90 Proof)'."""
    if not text:
        return None
    match = re.search(r"(\d{1,2}(?:\.\d+)?)\s*%", text)
    if match:
        return float(match.group(1))
    # Fall back to proof -> ABV (proof / 2).
    proof = re.search(r"(\d{1,3}(?:\.\d+)?)\s*proof", text, re.IGNORECASE)
    if proof:
        return float(proof.group(1)) / 2.0
    return None


def looks_like_abv(text: str | None) -> bool:
    """True if the string contains a plausible ABV/percentage figure."""
    return extract_abv(text) is not None
