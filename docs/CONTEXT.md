# CONTEXT — AI-Powered Alcohol Label Verification

> One-page snapshot. Keep this current; it's the first file a new contributor reads.

## Goal
A deployed, dead-simple web app that lets a TTB compliance agent verify an alcohol label
image against TTB requirements — checking brand name, ABV, and the Government Warning —
fast and with minimal clicks.

## Hard constraints (from the stakeholder brief)
- **≤ 5 seconds** per label (prior 30–40s vendor was abandoned).
- **Extreme UI simplicity** — usable by a non-technical 73-year-old; half the team is 50+.
- **Batch uploads** — 200–300 labels at once, with a per-label pass/fail summary.
- **Graceful errors** on angled / glare / unreadable photos.
- **Firewall reality** — production network blocks cloud-ML endpoints; relaxed for the
  prototype but documented as a migration concern.

## Two verification modes
- **Compare-to-fields** — agent supplies expected values; app flags mismatches.
- **Rule-check** — app validates TTB compliance from the image alone.

## Tech stack
- Backend: Python 3.11+, FastAPI, uvicorn.
- Extraction: Claude vision behind a swappable `ExtractionBackend` interface
  (local Tesseract stub for the air-gapped production path).
- Matching: `rapidfuzz` (fuzzy brand/type) + deterministic strict warning validator.
- Frontend: no-build vanilla HTML/CSS/JS, served statically by FastAPI (single service / URL).

## Status
See `docs/TASKS.md` for the live task board.

## Where things live
- `backend/app/` — API, extraction, comparison, rules.
- `frontend/` — static SPA.
- `docs/` — these living context docs.
