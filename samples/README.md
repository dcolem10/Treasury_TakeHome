# Sample labels & test plan

Synthetic TTB-style labels for exercising every verdict path. Regenerate with
`python samples/generate_samples.py`.

## Rule-check mode ("Check the label is complete")
Upload each file and confirm the result:

| File | Expected result | Why |
|------|-----------------|-----|
| `01_compliant.png` | **PASS** | All required fields present; warning exact + ALL CAPS. |
| `02_bad_warning_titlecase.png` | **FAIL** — Government Warning | Prefix is `Government Warning:` (title case), not ALL CAPS. |
| `03_missing_warning.png` | **FAIL** — Government Warning | No warning statement on the label. |
| `04_missing_net_contents.png` | **FAIL** — Net Contents | Required field absent. |
| `05_other_brand.png` | **PASS** | A second compliant label (different brand) for compare-mode demos. |

## Compare mode ("Compare to the application")
Use `01_compliant.png` and type values into the form:

| Brand name you type | Expected | Demonstrates |
|---------------------|----------|--------------|
| `Old Tom Distillery` | **PASS** (brand) | Fuzzy match forgives the case difference vs `OLD TOM DISTILLERY`. |
| `old tom distilery` (typo) | **PASS or near-match** | Fuzzy tolerance. |
| `Pirate's Cove Rum` | **FAIL** (brand) | Genuinely different brand. |

Also try **Alcohol content** `40% Alc./Vol.` against `01_compliant.png` → **FAIL** (label is 45%).

## Batch mode
Switch to **Check many labels**, select all five PNGs at once → the summary should show
**2 passed / 3 need review**, and the table should be sortable by result.

## Unreadable handling
Upload any non-label image (a photo, a screenshot) → expect a clear
"Couldn't read this image — resubmit a clearer photo" message, not an error.
