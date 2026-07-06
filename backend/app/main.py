"""FastAPI application: serves the API and the static frontend as one deployable."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .comparison.compare import build_verdict
from .config import settings
from .extraction import get_backend
from .extraction.base import LabelExtraction
from .extraction.textract_verify import crosscheck_warning, merge_witness
from .manifest import match_expected, parse_manifest
from .ratelimit import enforce_rate_limit
from .rules import EXTRACTION_FIELDS
from .schemas import BatchItem, BatchResponse, Verdict

app = FastAPI(title="TTB Label Verification", version="1.0.0")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if not request.url.path.startswith("/api/"):
        # Frontend assets: force revalidation so agents see new UI right after a deploy.
        response.headers["Cache-Control"] = "no-cache"
    return response

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB per image
MAX_BATCH_FILES = 300


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "extraction_backend": settings.EXTRACTION_BACKEND,
        "warning_crosscheck": settings.WARNING_CROSSCHECK,
    }


async def _extract(image_bytes: bytes, content_type: str) -> tuple[LabelExtraction, Optional[str]]:
    """Extract label fields, optionally cross-checked by Textract.

    The extraction backend and the (optional) Textract warning cross-check run
    concurrently off the event loop so the cross-check doesn't add to wall time.
    Returns the (possibly signal-merged) extraction and a cross-check note.
    """
    backend = get_backend()
    ctype = content_type or "image/jpeg"
    tasks = [asyncio.to_thread(backend.extract, image_bytes, ctype)]
    if settings.WARNING_CROSSCHECK:
        tasks.append(asyncio.to_thread(crosscheck_warning, image_bytes))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    extraction = results[0]
    if isinstance(extraction, BaseException):
        raise extraction

    note = None
    if len(results) > 1 and not isinstance(results[1], BaseException):
        extraction, note = merge_witness(extraction, results[1])
    return extraction, note


def _validate_image(data: bytes, content_type: Optional[str]) -> None:
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 15 MB limit.")
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Uploaded file is not an image.")


@app.post("/api/verify", response_model=Verdict)
async def verify(
    request: Request,
    image: UploadFile = File(...),
    mode: str = Form("rules"),
    brand_name: Optional[str] = Form(None),
    class_type: Optional[str] = Form(None),
    alcohol_content: Optional[str] = Form(None),
    net_contents: Optional[str] = Form(None),
    producer: Optional[str] = Form(None),
    country_of_origin: Optional[str] = Form(None),
) -> Verdict:
    if mode not in ("compare", "rules"):
        raise HTTPException(status_code=400, detail="mode must be 'compare' or 'rules'.")
    enforce_rate_limit(request, images=1)

    data = await image.read()
    _validate_image(data, image.content_type)

    started = time.perf_counter()
    extraction, crosscheck_note = await _extract(data, image.content_type or "image/jpeg")
    expected = {
        "brand_name": brand_name,
        "class_type": class_type,
        "alcohol_content": alcohol_content,
        "net_contents": net_contents,
        "producer": producer,
        "country_of_origin": country_of_origin,
    }
    verdict = build_verdict(
        extraction, mode, expected if mode == "compare" else None, crosscheck_note=crosscheck_note
    )
    verdict.elapsed_ms = int((time.perf_counter() - started) * 1000)
    return verdict


@app.post("/api/verify-batch", response_model=BatchResponse)
async def verify_batch(
    request: Request,
    images: list[UploadFile] = File(...),
    mode: str = Form("rules"),
    manifest: Optional[UploadFile] = File(None),
) -> BatchResponse:
    if not images:
        raise HTTPException(status_code=400, detail="No images uploaded.")
    if len(images) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=413, detail=f"Batch limited to {MAX_BATCH_FILES} images."
        )
    # A batch spends one rate-limit unit per image (each is a paid vision call).
    enforce_rate_limit(request, images=len(images))

    # If a manifest CSV is supplied, each matching image is compared to its row
    # (compare mode); unmatched images fall back to rule-check.
    manifest_map: dict[str, dict[str, str]] = {}
    if manifest is not None:
        try:
            manifest_map = parse_manifest(await manifest.read())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Manifest error: {exc}")

    started = time.perf_counter()
    payloads = [(img.filename or "image", await img.read(), img.content_type) for img in images]

    semaphore = asyncio.Semaphore(settings.BATCH_CONCURRENCY)

    async def process(filename: str, data: bytes, content_type: Optional[str]) -> BatchItem:
        async with semaphore:
            expected = match_expected(manifest_map, filename)
            item_mode = "compare" if expected else "rules"
            if not data:
                verdict = Verdict(
                    overall="unreadable", readable=False, mode=item_mode,
                    error="Empty file.",
                )
            else:
                item_start = time.perf_counter()
                extraction, crosscheck_note = await _extract(data, content_type or "image/jpeg")
                verdict = build_verdict(
                    extraction, item_mode, expected, crosscheck_note=crosscheck_note
                )
                verdict.elapsed_ms = int((time.perf_counter() - item_start) * 1000)
            return BatchItem(filename=filename, verdict=verdict)

    results = await asyncio.gather(*(process(f, d, c) for f, d, c in payloads))

    passed = sum(1 for r in results if r.verdict.overall == "pass")
    failed = sum(1 for r in results if r.verdict.overall == "fail")
    unreadable = sum(1 for r in results if r.verdict.overall == "unreadable")

    return BatchResponse(
        count=len(results),
        passed=passed,
        failed=failed,
        unreadable=unreadable,
        results=list(results),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


# --- Static frontend (mounted last so /api/* wins) ---
if FRONTEND_DIR.is_dir():

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
