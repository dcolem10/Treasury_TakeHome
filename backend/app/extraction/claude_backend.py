"""Claude vision extraction backend.

Sends the label image to a Claude vision model and asks for the TTB fields as strict JSON,
including the Government Warning transcribed *exactly* as printed (so the downstream strict
validator can judge caps/wording). The model only reads text — it makes no pass/fail call.
"""
from __future__ import annotations

import base64
import json
from typing import Optional

from ..config import settings
from ..rules import EXTRACTION_FIELDS
from .base import ExtractionBackend, LabelExtraction

_SYSTEM = (
    "You are an OCR and data-extraction engine for U.S. alcohol beverage labels (TTB COLA). "
    "Transcribe exactly what is printed. Do not correct spelling, casing, or punctuation. "
    "Never invent values. If a field is not visible, use null."
)

_INSTRUCTION = (
    "Extract the following fields from this label image and return ONLY a JSON object with "
    "these exact keys:\n"
    "- brand_name\n- class_type (class/type designation, e.g. 'Kentucky Straight Bourbon Whiskey')\n"
    "- alcohol_content (exactly as printed, e.g. '45% Alc./Vol. (90 Proof)')\n"
    "- net_contents (e.g. '750 mL')\n- producer (name and address of bottler/producer)\n"
    "- country_of_origin (or null if not present)\n"
    "- government_warning (transcribe the FULL warning statement EXACTLY as printed, preserving "
    "capitalization and punctuation; null if absent)\n"
    "- readable (true if the label text is legible, false if the image is too blurry/dark/angled to read)\n\n"
    "Return only the JSON object, no prose, no markdown fences."
)

# Media types Claude vision accepts.
_SUPPORTED = {"image/jpeg", "image/png", "image/gif", "image/webp"}


class ClaudeVisionBackend(ExtractionBackend):
    name = "claude"

    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set; the Claude extraction backend cannot start."
            )
        # Imported lazily so the module loads even if anthropic isn't installed.
        from anthropic import Anthropic

        self._client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def extract(self, image_bytes: bytes, content_type: str) -> LabelExtraction:
        media_type = content_type if content_type in _SUPPORTED else "image/jpeg"
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")

        try:
            message = self._client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=1024,
                system=_SYSTEM,
                timeout=settings.EXTRACTION_TIMEOUT_S,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": _INSTRUCTION},
                        ],
                    }
                ],
            )
        except Exception as exc:  # network/API failure -> unreadable, not a crash
            return LabelExtraction(
                readable=False, error=f"Extraction service error: {exc}"
            )

        text = "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        ).strip()

        data = _parse_json(text)
        if data is None:
            return LabelExtraction(
                readable=False,
                raw_text=text,
                error="Could not parse extraction output.",
            )

        readable = bool(data.get("readable", True))
        fields = {key: _clean(data.get(key)) for key in EXTRACTION_FIELDS}
        if readable and not any(fields.values()):
            readable = False

        return LabelExtraction(
            readable=readable,
            fields=fields,
            raw_text=text,
            error=None if readable else "Label text could not be read clearly.",
        )


def _clean(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_json(text: str) -> Optional[dict]:
    """Tolerate stray markdown fences or surrounding prose."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None
