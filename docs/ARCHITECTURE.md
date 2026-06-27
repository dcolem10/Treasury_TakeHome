# ARCHITECTURE

## Overview
Single FastAPI service. It serves the static frontend AND the JSON API, so the whole app
is one deployable behind one URL.

```
Browser (vanilla SPA)
   │  multipart upload (image[, expected fields])
   ▼
FastAPI  ──►  ExtractionBackend (interface)
   │              ├─ ClaudeVisionBackend   (prototype: OCR + field extraction in one pass)
   │              └─ TesseractBackend       (stub: air-gapped production path)
   │
   ├──►  Comparison engine (pure, deterministic)
   │         ├─ fuzzy.py    normalize + rapidfuzz similarity (brand / class-type)
   │         ├─ warning.py  strict canonical-text + ALL-CAPS validation
   │         └─ compare.py  compare_to_fields() / rule_check()  → Verdict
   │
   ▼
JSON Verdict  ──►  Browser renders plain checklist / batch table
```

## Data flow
1. Frontend sends an image (and, in compare mode, the expected field values).
2. `ExtractionBackend.extract(image_bytes)` returns a `LabelExtraction` (fields + raw text +
   `readable` flag). Unreadable images short-circuit to a clear error verdict.
3. The deterministic comparator produces a `Verdict`: overall pass/fail + per-check rows,
   each with status (`pass` / `fail` / `warn`) and a one-line human reason.
4. Batch: `/verify-batch` fans out across a bounded worker pool to hold the per-label budget.

## Key design decisions
- **Verdict logic is deterministic code, not the LLM.** The model only extracts text/fields;
  pass/fail is computed in `comparison/` so results are explainable, testable, and stable.
- **Extraction is swappable** behind one interface — the cloud→local swap is config-only.
- **No persistence.** Images are processed in-memory and discarded (PII-safe prototype).

## Deployment
Single container running `uvicorn`. Needs `ANTHROPIC_API_KEY` and outbound HTTPS to the
Anthropic API. Frontend assets served by FastAPI from `frontend/`.
