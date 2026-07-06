"""Pydantic models for API requests/responses. Mirrors docs/API_CONTRACT.md."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

CheckStatus = Literal["pass", "fail", "warn"]
Overall = Literal["pass", "fail", "unreadable"]
Mode = Literal["compare", "rules"]


class CheckResult(BaseModel):
    field: str
    label: str
    status: CheckStatus
    expected: Optional[str] = None
    found: Optional[str] = None
    reason: str


class ExtractedFields(BaseModel):
    brand_name: Optional[str] = None
    class_type: Optional[str] = None
    alcohol_content: Optional[str] = None
    net_contents: Optional[str] = None
    producer: Optional[str] = None
    country_of_origin: Optional[str] = None
    government_warning: Optional[str] = None


class Verdict(BaseModel):
    overall: Overall
    readable: bool
    mode: Mode
    checks: list[CheckResult] = []
    extracted: ExtractedFields = ExtractedFields()
    elapsed_ms: int = 0
    error: Optional[str] = None
    # Non-blocking note when the image was readable but marginal quality.
    quality_note: Optional[str] = None
    # What the Textract cross-check observed about the warning (when enabled).
    crosscheck_note: Optional[str] = None


class BatchItem(BaseModel):
    filename: str
    verdict: Verdict


class BatchResponse(BaseModel):
    count: int
    passed: int
    failed: int
    unreadable: int
    results: list[BatchItem]
    elapsed_ms: int
