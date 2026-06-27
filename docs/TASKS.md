# TASK BOARD

Status: ☐ todo · ◐ in progress · ☑ done

| # | Task | Status | Depends on | Notes |
|---|------|--------|-----------|-------|
| T1 | Repo scaffold + context docs | ☑ | — | structure, `.gitignore`, six `docs/*.md` |
| T2 | Verification contract & TTB rules spec | ☑ | T1 | schemas + RULES.md + canonical warning |
| T3 | Extraction layer (Claude vision + Tesseract stub) | ☑ | T2 | interface + backends |
| T4 | Deterministic comparison engine | ☑ | T2 | fuzzy + strict warning + ABV |
| T5 | Backend API (`/verify`, `/verify-batch`) | ☑ | T3, T4 | bounded concurrency |
| T6 | Single-label UI | ☑ | T2, T5 | upload, mode toggle, checklist |
| T7 | Batch upload UI | ☑ | T2, T5 | results table |
| T8 | Test labels + automated tests + latency check | ☑ | T4, T5 | 18 pytest cases green |
| T9 | Deploy + top-level README | ◐ | T5–T8 | Dockerfile + README done; live URL pending user |

## Log
- T1 done: scaffold + six context docs created.
- T2 done: schemas (`API_CONTRACT.md`) and rules (`RULES.md`) pinned, incl. canonical warning.
- T3 done: `ExtractionBackend` interface + Claude vision backend + Tesseract stub + factory.
- T4 done: fuzzy/normalize, strict warning validator, compare + rule-check verdict builder.
- T5 done: `/api/verify`, `/api/verify-batch` (bounded concurrency), `/api/health`, static serving.
- T6/T7 done: single + batch UI (tabs, mode toggle, plain checklist, sortable batch table).
- T8 done: 18 unit tests pass; end-to-end + batch smoke-tested with a fake backend.
- T9: Dockerfile, `.env.example`, README, assignment preserved at `docs/ASSIGNMENT.md`.
  Remaining: deploy to a host with `ANTHROPIC_API_KEY` to capture the live URL (needs creds).
