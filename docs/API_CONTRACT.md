# API CONTRACT

All endpoints return JSON. Images are sent as multipart form-data. No auth on the prototype.

## Shared types

### `CheckResult`
```json
{
  "field": "government_warning",
  "label": "Government Warning",
  "status": "pass | fail | warn",
  "expected": "…",        // present in compare mode; null otherwise
  "found": "…",           // what was read off the label (may be null)
  "reason": "Human-readable one-liner explaining the status"
}
```

### `Verdict`
```json
{
  "overall": "pass | fail | unreadable",
  "readable": true,
  "mode": "compare | rules",
  "checks": [ CheckResult, ... ],
  "extracted": {           // raw extraction echoed back for transparency
    "brand_name": "…",
    "class_type": "…",
    "alcohol_content": "…",
    "net_contents": "…",
    "producer": "…",
    "country_of_origin": "…",
    "government_warning": "…"
  },
  "elapsed_ms": 1234,
  "error": null,           // populated when overall = "unreadable"
  "quality_note": null     // set when the image was readable but marginal (angle/glare/dim)
}
```

The Government Warning check may be `warn` (not just pass/fail) when the text is exact but
the warning looks non-bold, unusually small, or buried — a prominence flag for the agent.

## `POST /api/verify`
Multipart fields:
- `image` (file, required)
- `mode` ("compare" | "rules", default "rules")
- Expected values (used only in compare mode, all optional):
  `brand_name`, `class_type`, `alcohol_content`, `net_contents`, `producer`,
  `country_of_origin`

Returns: `Verdict`.

## `POST /api/verify-batch`
Multipart fields:
- `images` (multiple files, required)
- `mode` ("compare" | "rules", default "rules")
- `manifest` (optional CSV file) — an application list. Each image whose filename matches a
  row is verified in **compare** mode against that row's expected values; unmatched images
  fall back to **rule-check**. Columns (header row, case-insensitive; only `filename`
  required): `filename, brand_name, class_type, alcohol_content, net_contents, producer,
  country_of_origin`. A CSV with no `filename` column returns 400.

Each result's `verdict.mode` reports how that file was checked (`compare` vs `rules`).

Returns:
```json
{
  "count": 200,
  "passed": 150,
  "failed": 45,
  "unreadable": 5,
  "results": [ { "filename": "…", "verdict": Verdict }, ... ],
  "elapsed_ms": 4200
}
```

## `GET /api/health`
`{ "status": "ok", "extraction_backend": "claude | tesseract" }`
