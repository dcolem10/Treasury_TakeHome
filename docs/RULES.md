# TTB RULES & MATCHING SPEC

> Source of truth for what "compliant" and "a match" mean. Tunable thresholds live here.

## Government Warning — exact text (27 CFR § 16.21)
The statement must appear **verbatim**. `GOVERNMENT WARNING:` must be in **all caps** and
bold (bold is a visual property; the prototype validates caps + exact wording from OCR text).

```
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink
alcoholic beverages during pregnancy because of the risk of birth defects.
(2) Consumption of alcoholic beverages impairs your ability to drive a car or
operate machinery, and may cause health problems.
```

### Warning validation logic (`comparison/warning.py`)
Normalize whitespace (collapse runs, including newlines) before comparing, then check:
1. **Prefix caps** — the literal `GOVERNMENT WARNING:` substring is present in ALL CAPS.
   - Title-case `Government Warning:` → **fail** with reason "must be in all capital letters".
2. **Exact body** — the full normalized text equals the canonical statement (case-sensitive
   on the prefix, case-insensitive tolerance is NOT applied to the prefix).
   - Missing → **fail** "Government Warning statement not found".
   - Reworded / partial → **fail** "Warning text does not match the required statement".
3. **Prominence** (visual signals from the extraction backend, optional). When text + caps
   are correct but the warning appears **not bold**, **unusually small**, or **buried** in
   other text → **warn** (not fail). TTB requires bold + a minimum type size, but these
   visual reads are heuristic, so we flag for the agent's eye rather than auto-rejecting.
4. Pass only when prefix-caps AND exact-body hold AND no prominence issue is flagged.

## Image quality (messy-photo handling)
The extraction backend reports `image_quality`: `clear` | `marginal` | `unreadable`.
- `unreadable` → the whole verdict short-circuits to a clear "resubmit a clearer photo".
- `marginal` (angle/glare/dim but legible) → the label is still evaluated, and the verdict
  carries a non-blocking `quality_note` telling the agent to double-check. The extraction
  prompt explicitly instructs the model to try hard before declaring a photo unreadable.

## Application manifest (batch compare)
`app/manifest.py` parses an optional CSV of expected values and matches rows to uploaded
images by filename (case-insensitive, path-insensitive). Matched images run compare mode;
unmatched images run rule-check. Only `filename` is required; blank cells are not checked.

## Required fields (rule-check mode)
Per the brief; some are beverage-type dependent (noted as a prototype simplification):
- `brand_name` — required
- `class_type` — required
- `alcohol_content` — required (format: a percentage, optionally with proof, e.g.
  `45% Alc./Vol. (90 Proof)`); validated with a permissive regex for a `%`/ABV figure.
- `net_contents` — required
- `producer` (name/address of bottler/producer) — required
- `country_of_origin` — required **only for imports** (not failed if absent in v1; flagged `warn`)
- `government_warning` — required, validated as above

## Fuzzy matching (compare mode — `comparison/fuzzy.py`)
Applies to free-text fields where human judgment forgives trivial differences
(`STONE'S THROW` == `Stone's Throw`):
- Normalize: lowercase, strip accents, collapse whitespace, remove punctuation.
- Score with `rapidfuzz.fuzz.token_sort_ratio`.
- **Threshold = 88** → `pass`; **80–87** → `warn` (near match, agent should eyeball);
  **< 80** → `fail`. Thresholds are tunable here.

### Per-field match strategy
| Field | Strategy |
|-------|----------|
| brand_name | fuzzy (token_sort_ratio) |
| class_type | fuzzy |
| producer | fuzzy |
| net_contents | normalized exact (units-aware: `750 mL` == `750ml`) |
| alcohol_content | numeric ABV extracted and compared with ±0.0 tolerance (configurable) |
| country_of_origin | normalized exact |
| government_warning | strict (see above) — never fuzzy |
