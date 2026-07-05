"""Generate synthetic TTB-style label images for testing.

Each label is plain, high-contrast text so any OCR/vision backend reads it reliably. The set
deliberately exercises every verdict path (compliant, bad warning, missing field, etc.).

Run:  python samples/generate_samples.py
Output: samples/*.png
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

OUT = Path(__file__).resolve().parent
FONT_DIR = "/usr/share/fonts/truetype/dejavu"

WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

W, H = 850, 1150
CREAM = (247, 244, 236)
INK = (28, 26, 24)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(f"{FONT_DIR}/{name}", size)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_label(filename: str, *, brand, class_type, abv, net, producer, warning,
               origin=None, warning_size=20, save=True):
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([18, 18, W - 18, H - 18], outline=INK, width=4)

    def centered(text, fnt, y, fill=INK):
        w = d.textlength(text, font=fnt)
        d.text(((W - w) / 2, y), text, font=fnt, fill=fill)

    centered(brand, font("DejaVuSans-Bold.ttf", 52), 70)
    centered(class_type, font("DejaVuSans.ttf", 30), 150)
    d.line([120, 210, W - 120, 210], fill=INK, width=2)

    centered(abv, font("DejaVuSans-Bold.ttf", 34), 250)
    centered(net, font("DejaVuSans.ttf", 30), 310)

    y = 400
    for line in wrap(d, producer, font("DejaVuSans.ttf", 24), W - 200):
        centered(line, font("DejaVuSans.ttf", 24), y)
        y += 34
    if origin:
        centered(origin, font("DejaVuSans.ttf", 24), y + 10)

    # Warning block at the bottom (smaller text, as on real labels).
    if warning:
        wf = font("DejaVuSans.ttf", warning_size)
        wy = H - 270
        for line in wrap(d, warning, wf, W - 120):
            d.text((60, wy), line, font=wf, fill=INK)
            wy += warning_size + 8

    if save:
        img.save(OUT / filename)
        print("wrote", filename)
    return img


BASE = dict(
    brand="OLD TOM DISTILLERY",
    class_type="Kentucky Straight Bourbon Whiskey",
    abv="45% Alc./Vol. (90 Proof)",
    net="750 mL",
    producer="Distilled & Bottled by Old Tom Distillery, Bardstown, KY",
)

# 1) Fully compliant -> rule-check PASS.
make_label("01_compliant.png", warning=WARNING, **BASE)

# 2) Warning prefix in Title Case -> FAIL (must be ALL CAPS).
make_label(
    "02_bad_warning_titlecase.png",
    warning=WARNING.replace("GOVERNMENT WARNING:", "Government Warning:"),
    **BASE,
)

# 3) No warning at all -> FAIL (warning missing).
make_label("03_missing_warning.png", warning=None, **BASE)

# 4) Missing net contents -> FAIL (required field). Compliant warning.
NO_NET = {k: v for k, v in BASE.items() if k != "net"}
make_label("04_missing_net_contents.png", net="", warning=WARNING, **NO_NET)

# 5) Different brand, for compare-mode fuzzy demos -> rule-check PASS on its own.
make_label(
    "05_other_brand.png",
    brand="STONE'S THROW",
    class_type="Straight Rye Whiskey",
    abv="50% Alc./Vol. (100 Proof)",
    net="750 mL",
    producer="Bottled by Stone's Throw Spirits, Asheville, NC",
    warning=WARNING,
)

# 6) Correct warning text but printed tiny -> prominence WARN (text OK, looks small).
#    (Vision-dependent: confirms F2 on the live deployment.)
make_label("06_tiny_warning.png", warning=WARNING, warning_size=9, **BASE)

# 7) Compliant label degraded: rotated + lower contrast + glare -> messy-photo handling.
#    Should still read (image_quality "marginal") rather than bounce. Confirm F4 live.
clean = make_label("07_low_quality.png", warning=WARNING, save=False, **BASE)
clean = ImageEnhance.Contrast(clean).enhance(0.55)
clean = ImageEnhance.Brightness(clean).enhance(1.15)
glare = Image.new("RGB", clean.size, (255, 255, 255))
mask = Image.new("L", clean.size, 0)
ImageDraw.Draw(mask).ellipse([420, 120, 900, 620], fill=110)
clean = Image.composite(glare, clean, mask)
clean = clean.rotate(-8, expand=True, fillcolor=(30, 30, 30))
clean.save(OUT / "07_low_quality.png")
print("wrote 07_low_quality.png")
