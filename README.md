# Label Check — AI-Powered Alcohol Label Verification

A prototype web app for TTB compliance agents. Upload a label photo and the app reads it,
then checks it against TTB requirements — brand name, alcohol content, required fields, and
(strictly) the Government Warning statement. It works in two ways:

- **Check the label is complete** (rule-check) — validates the label on its own.
- **Compare to the application** — the agent types the expected values; the app flags
  anything that doesn't match, forgiving trivial differences like `STONE'S THROW` vs
  `Stone's Throw`.

It also handles **batch uploads** (up to 300 labels at once) with a sortable pass/fail table.

> The original take-home brief is preserved at [`docs/ASSIGNMENT.md`](docs/ASSIGNMENT.md).

## Quick start (local)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Provide your key (the Claude vision backend needs it):
export ANTHROPIC_API_KEY=sk-ant-...

uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000>.

Run the tests (no API key required — they exercise the deterministic engine):

```bash
cd backend && source .venv/bin/activate && python -m pytest -q
```

## Run with Docker

```bash
docker build -t label-check .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... label-check
```

## Deploy

The whole app is one container (FastAPI serves the API **and** the static frontend), so any
container host works (Render, Fly.io, Azure Container Apps, Cloud Run). Set
`ANTHROPIC_API_KEY` and bind to `$PORT`. The included `Dockerfile` does both.

## How it works

```
Browser (vanilla SPA)  ──►  FastAPI  ──►  ExtractionBackend (Claude vision | Tesseract)
                                  └────►  Comparison engine (fuzzy + strict warning) ──► Verdict
```

1. **Extraction** — the label image goes to a Claude vision model, which transcribes the TTB
   fields as strict JSON (including the warning, copied verbatim). This is hidden behind an
   `ExtractionBackend` interface so a local OCR engine can replace it for an air-gapped
   network — swapping is a config change, not a rewrite.
2. **Verdict** — all pass/fail logic is **deterministic Python**, not the model: fuzzy
   similarity for free-text fields, numeric comparison for ABV, and a **strict** validator for
   the Government Warning (exact statutory wording + `GOVERNMENT WARNING:` in all caps).
3. **Response** — a plain checklist (green / red / amber, each with a one-line reason).

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/RULES.md`](docs/RULES.md), and
[`docs/DECISIONS.md`](docs/DECISIONS.md) for details.

## Design choices, made for the stakeholders

| Requirement (from the interviews) | How it's met |
|-----------------------------------|--------------|
| Results in **≤ 5 seconds** | One vision call per label; deterministic verdict is sub-ms. Elapsed time is shown on every result. |
| **Anyone can use it** (mixed tech comfort, 50+) | One screen, big targets, plain-language pass/fail, no jargon. |
| **Batch** for big importers | Up to 300 files, processed concurrently, sortable results table. |
| **Strict warning** check | Never fuzzy-matched; title-case `Government Warning` fails by design. |
| Agent **judgment** on trivial diffs | Fuzzy matching forgives case/punctuation/spacing on brand/type. |
| **Bad photos** | Unreadable images return a clear "resubmit a clearer photo" message, not a crash. |
| **Firewall** in production | Cloud backend is swappable for a local Tesseract backend via `EXTRACTION_BACKEND`. |

## Assumptions & limitations

- **Cloud for the prototype.** Production needs an on-prem/air-gapped model behind the same
  `ExtractionBackend` interface (TTB blocks cloud-ML endpoints; FedRAMP). Documented, not built.
- **Bold** isn't reliably recoverable from OCR text, so the warning check enforces ALL-CAPS
  prefix + exact wording; bold is a known gap.
- Beverage-type-specific ABV exceptions (beer/wine) are modeled simply.
- Country of origin absent → a **warning**, not a failure (import status is unknown in v1).
- Batch v1 runs rule-check only (no per-file expected values).
- No persistence — images are processed in memory and discarded (PII-safe).

## Project layout

```
backend/app/
  main.py            FastAPI routes + static serving
  extraction/        ExtractionBackend interface + Claude / Tesseract backends
  comparison/        fuzzy.py, warning.py (strict), compare.py (verdict)
  rules.py           canonical warning text + required fields
frontend/            no-build HTML/CSS/JS SPA
docs/                CONTEXT, ARCHITECTURE, API_CONTRACT, RULES, DECISIONS, TASKS, ASSIGNMENT
```
