"""Textract warning cross-check: witness extraction, geometry, fail-closed merge.

All mocked — no AWS calls. Confirms the second witness catches exactly the
canonicalization failure mode that slipped past the LLM-only path.
"""
import app.extraction.textract_verify as tv
from app.extraction.base import LabelExtraction
from app.extraction.textract_verify import merge_witness, witness_from_blocks
from app.rules import GOVERNMENT_WARNING_TEXT


def _blocks(heading: str, body_tail: str = None, heading_height=0.02, other_height=0.02):
    """Build minimal Textract blocks: a brand line + the warning, with word geometry."""
    tail = body_tail if body_tail is not None else GOVERNMENT_WARNING_TEXT.split(":", 1)[1].strip()
    warning_line = f"{heading} {tail}"
    lines = ["OLD TOM DISTILLERY", warning_line]
    blocks = [{"BlockType": "LINE", "Text": t} for t in lines]
    # brand words (other_height) + warning words (heading_height for the heading tokens)
    for w in "OLD TOM DISTILLERY".split():
        blocks.append(_word(w, other_height))
    for w in heading.split():
        blocks.append(_word(w, heading_height))
    for w in tail.split():
        blocks.append(_word(w, heading_height))
    return blocks


def _word(text, height):
    return {"BlockType": "WORD", "Text": text, "Geometry": {"BoundingBox": {"Height": height}}}


# ---- witness extraction ----
def test_witness_reads_title_case_heading_literally():
    w = witness_from_blocks(_blocks("Government Warning:"))
    assert w.found
    assert w.heading_all_caps is False          # the whole point: OCR doesn't up-case
    assert not w.differs_from_standard          # only casing differs; wording matches


def test_witness_all_caps_heading_passes():
    w = witness_from_blocks(_blocks("GOVERNMENT WARNING:"))
    assert w.heading_all_caps is True
    assert w.differs_from_standard is False


def test_witness_detects_wording_deviation():
    w = witness_from_blocks(_blocks("GOVERNMENT WARNING:", body_tail="Drinking is bad for you."))
    assert w.differs_from_standard is True


def test_witness_geometry_flags_small_warning():
    # warning words much shorter than the brand words -> "small"
    w = witness_from_blocks(_blocks("GOVERNMENT WARNING:", heading_height=0.006, other_height=0.03))
    assert w.prominence == "small"
    assert w.height_ratio < 0.6


def test_witness_absent_when_no_warning():
    blocks = [{"BlockType": "LINE", "Text": "OLD TOM DISTILLERY"}, _word("OLD", 0.02)]
    assert witness_from_blocks(blocks).found is False


# ---- fail-closed merge (the regression scenario) ----
def _extraction(**kw):
    fields = {"government_warning": GOVERNMENT_WARNING_TEXT}
    return LabelExtraction(readable=True, fields=fields, **kw)


def test_merge_overrides_llm_canonicalization():
    # LLM laundered casing (claims all-caps); Textract saw title case -> fail-closed.
    ext = _extraction(warning_heading_all_caps=True)
    w = witness_from_blocks(_blocks("Government Warning:"))
    merged, note = merge_witness(ext, w)
    assert merged.warning_heading_all_caps is False
    assert note and "not all caps" in note


def test_merge_noop_when_sources_agree():
    ext = _extraction(warning_heading_all_caps=True)
    w = witness_from_blocks(_blocks("GOVERNMENT WARNING:"))
    merged, note = merge_witness(ext, w)
    assert merged.warning_heading_all_caps is True
    assert note is None


def test_merge_handles_none_witness():
    ext = _extraction()
    merged, note = merge_witness(ext, None)
    assert merged is ext and note is None


# ---- disabled / unavailable path ----
def test_crosscheck_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(tv.settings, "WARNING_CROSSCHECK", False)
    assert tv.crosscheck_warning(b"whatever") is None


def test_crosscheck_client_error_returns_none(monkeypatch):
    monkeypatch.setattr(tv.settings, "WARNING_CROSSCHECK", True)

    class Boom:
        def detect_document_text(self, **_):
            raise RuntimeError("no creds")

    monkeypatch.setattr(tv, "get_textract_client", lambda: Boom())
    assert tv.crosscheck_warning(b"img") is None


# ---- full endpoint: the regression, defended by the cross-check ----
def test_endpoint_crosscheck_catches_laundered_casing(monkeypatch):
    """LLM reports canonical ALL-CAPS (laundered); Textract sees title case -> fail."""
    import app.main as main
    from app.extraction.base import ExtractionBackend
    from fastapi.testclient import TestClient

    class Backend(ExtractionBackend):
        name = "launder"

        def extract(self, image_bytes, content_type):
            return LabelExtraction(
                readable=True,
                fields={
                    "brand_name": "Old Tom Distillery",
                    "class_type": "Kentucky Straight Bourbon Whiskey",
                    "alcohol_content": "45% Alc./Vol. (90 Proof)",
                    "net_contents": "750 mL",
                    "producer": "Old Tom Distillery, KY",
                    "government_warning": GOVERNMENT_WARNING_TEXT,  # canonicalized
                },
                warning_heading_all_caps=True,   # the laundering
                warning_differs_from_standard=False,
            )

    class FakeTextract:
        def detect_document_text(self, **_):
            return {"Blocks": _blocks("Government Warning:")}

    monkeypatch.setattr(main, "get_backend", lambda: Backend())
    monkeypatch.setattr(main.settings, "WARNING_CROSSCHECK", True)
    monkeypatch.setattr(tv, "get_textract_client", lambda: FakeTextract())

    c = TestClient(main.app)
    r = c.post("/api/verify", data={"mode": "rules"},
               files={"image": ("02.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")})
    body = r.json()
    warning = next(x for x in body["checks"] if x["field"] == "government_warning")
    assert warning["status"] == "fail"
    assert body["overall"] == "fail"
    assert body["crosscheck_note"] and "not all caps" in body["crosscheck_note"]
