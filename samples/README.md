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
| `06_tiny_warning.png` | **PASS with a ⚠ check** | Warning text is correct but printed tiny → prominence **warn** (verify by eye). *Vision-dependent.* |
| `07_low_quality.png` | **PASS + 📷 quality note** | Angled, glare, low-contrast — should still read, with a "low quality, double-check" note rather than bouncing. *Vision-dependent.* |

> "*Vision-dependent*" rows rely on the live vision model's visual judgment (bold/size,
> image quality). Confirm those on the **deployed** site, where the model runs with a key.

## Compare mode ("Compare to the application")
Use `01_compliant.png` and type values into the form:

| Brand name you type | Expected | Demonstrates |
|---------------------|----------|--------------|
| `Old Tom Distillery` | **PASS** (brand) | Fuzzy match forgives the case difference vs `OLD TOM DISTILLERY`. |
| `old tom distilery` (typo) | **PASS or near-match** | Fuzzy tolerance. |
| `Pirate's Cove Rum` | **FAIL** (brand) | Genuinely different brand. |

Also try **Alcohol content** `40% Alc./Vol.` against `01_compliant.png` → **FAIL** (label is 45%).

## Batch mode + application manifest
Switch to **Check many labels**, select all seven PNGs, and attach
`samples/manifest_example.csv` as the application list. Expected:

- `01_compliant.png` → **compare** vs the manifest → **Pass** (values match, fuzzy-tolerant).
- `05_other_brand.png` → **compare** → **Review** (manifest brand is `WRONG BRAND NAME`).
- The rest → no manifest row → **completeness** (rule-check).

Without a manifest, every file is just rule-checked. The results table is sortable, and
**Download results (CSV)** / **Print** export the summary for the agent's queue.

## Unreadable handling
Upload any non-label image (a random photo, a screenshot) → expect a clear
"Couldn't read this image — resubmit a clearer photo" message, not an error.
