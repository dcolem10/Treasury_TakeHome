# DECISIONS & ASSUMPTIONS (ADR-style log)

Append new decisions at the top. Each entry: context → decision → consequence.

## D1 — Tech stack: FastAPI + no-build vanilla SPA
- **Context:** Need a deployable prototype with a single URL, dead-simple UI, and easy ops.
- **Decision:** Python/FastAPI backend that also serves a static HTML/CSS/JS frontend. No
  Node/npm build step.
- **Consequence:** One container, one deploy, no build toolchain. A heavier framework (React)
  is unnecessary for this UI and would complicate deployment. Batch table is built in plain JS.

## D2 — Cloud vision for the prototype, behind a swappable interface
- **Context:** TTB's production network blocks cloud-ML endpoints, but Marcus relaxed this for
  the prototype ("just don't do anything crazy"). The 5s budget and bad-photo robustness favor
  a vision LLM.
- **Decision:** `ClaudeVisionBackend` for OCR + structured field extraction in one pass, hidden
  behind an `ExtractionBackend` interface. A `TesseractBackend` stub documents the local path.
- **Consequence:** Production migration is a config-level swap, not a rewrite. Documented as the
  key firewall/FedRAMP trade-off.

## D3 — Verdict computed in deterministic code, not the LLM
- **Context:** Results must be explainable and stable for compliance use.
- **Decision:** The model only extracts text/fields. Pass/fail (fuzzy + strict warning) is pure
  Python in `comparison/`.
- **Consequence:** Fully unit-testable verdicts; no model nondeterminism in the compliance call.

## D4 — Government Warning canonical text from 27 CFR § 16.21
- **Decision:** Pin the statutory text verbatim in `rules.py` / `docs/RULES.md`.
- **Consequence:** Strict validation has an authoritative reference. Bold is a visual property
  not reliably recoverable from OCR text, so the prototype enforces ALL-CAPS prefix + exact
  wording and notes bold as a known limitation.

## D5 — No persistence (PII-safe prototype)
- **Decision:** Images processed in-memory and discarded; nothing stored.
- **Consequence:** Matches Marcus's "we're not storing anything sensitive" guidance; revisit for
  production (retention policy, audit log).

## Assumptions / known simplifications
- Beverage-type-specific rules (beer/wine/spirits ABV exceptions) modeled at a basic level.
- Country-of-origin absence is a `warn`, not a hard fail, since import status is unknown in v1.
- Batch v1 runs rule-check only (no per-file expected values).
