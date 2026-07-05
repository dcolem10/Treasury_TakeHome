"""FastAPI application: serves the API and the static frontend as one deployable."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .comparison.compare import build_verdict
from .config import settings
from .extraction import get_backend
from .extraction.base import LabelExtraction
from .manifest import match_expected, parse_manifest
from .rules import EXTRACTION_FIELDS
from .schemas import BatchItem, BatchResponse, Verdict

app = FastAPI(title="TTB Label Verification", version="1.0.0")

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB per image
MAX_BATCH_FILES = 300


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "extraction_backend": settings.EXTRACTION_BACKEND}


async def _extract(image_bytes: bytes, content_type: str) -> LabelExtraction:
    """Run the (sync) extraction backend off the event loop."""
    backend = get_backend()
    return await asyncio.to_thread(backend.extract, image_bytes, content_type or "image/jpeg")


def _validate_image(data: bytes, content_type: Optional[str]) -> None:
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 15 MB limit.")
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Uploaded file is not an image.")


@app.post("/api/verify", response_model=Verdict)
async def verify(
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

    data = await image.read()
    _validate_image(data, image.content_type)

    started = time.perf_counter()
    extraction = await _extract(data, image.content_type or "image/jpeg")
    expected = {
        "brand_name": brand_name,
        "class_type": class_type,
        "alcohol_content": alcohol_content,
        "net_contents": net_contents,
        "producer": producer,
        "country_of_origin": country_of_origin,
    }
    verdict = build_verdict(extraction, mode, expected if mode == "compare" else None)
    verdict.elapsed_ms = int((time.perf_counter() - started) * 1000)
    return verdict


@app.post("/api/verify-batch", response_model=BatchResponse)
async def verify_batch(
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
                extraction = await _extract(data, content_type or "image/jpeg")
                verdict = build_verdict(extraction, item_mode, expected)
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
