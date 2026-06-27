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
  "error": null            // populated when overall = "unreadable"
}
```

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
- (compare-mode expected values are out of scope for batch v1 — batch runs rule-check)

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
