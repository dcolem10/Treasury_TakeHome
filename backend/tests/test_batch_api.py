"""End-to-end batch endpoint with a stub backend (no API key needed).

Exercises manifest-driven compare mode mixed with rule-check fallback.
"""
import app.main as main
from app.extraction.base import ExtractionBackend, LabelExtraction
from app.rules import GOVERNMENT_WARNING_TEXT
from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


class StubBackend(ExtractionBackend):
    """Returns a fixed compliant Old Tom label for every image."""

    name = "stub"

    def extract(self, image_bytes, content_type):
        return LabelExtraction(readable=True, fields={
            "brand_name": "OLD TOM DISTILLERY",
            "class_type": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": "45% Alc./Vol. (90 Proof)",
            "net_contents": "750 mL",
            "producer": "Old Tom Distillery, Bardstown, KY",
            "country_of_origin": None,
            "government_warning": GOVERNMENT_WARNING_TEXT,
        })


def client(monkeypatch):
    monkeypatch.setattr(main, "get_backend", lambda: StubBackend())
    return TestClient(main.app)


def test_batch_rules_only(monkeypatch):
    c = client(monkeypatch)
    files = [("images", ("01.png", PNG, "image/png")),
             ("images", ("02.png", PNG, "image/png"))]
    r = c.post("/api/verify-batch", files=files, data={"mode": "rules"})
    body = r.json()
    assert body["count"] == 2 and body["passed"] == 2
    assert all(item["verdict"]["mode"] == "rules" for item in body["results"])


def test_batch_with_manifest_compare(monkeypatch):
    c = client(monkeypatch)
    # 01 matches the label (case-different brand -> fuzzy pass);
    # 02 has a wrong brand -> compare fail; 03 has no manifest row -> rule-check pass.
    manifest = (
        b"filename,brand_name\n"
        b"01.png,Old Tom Distillery\n"
        b"02.png,Completely Different Brand\n"
    )
    files = [
        ("images", ("01.png", PNG, "image/png")),
        ("images", ("02.png", PNG, "image/png")),
        ("images", ("03.png", PNG, "image/png")),
        ("manifest", ("apps.csv", manifest, "text/csv")),
    ]
    r = c.post("/api/verify-batch", files=files)
    body = r.json()
    by_name = {i["filename"]: i["verdict"] for i in body["results"]}

    assert by_name["01.png"]["mode"] == "compare" and by_name["01.png"]["overall"] == "pass"
    assert by_name["02.png"]["mode"] == "compare" and by_name["02.png"]["overall"] == "fail"
    assert by_name["03.png"]["mode"] == "rules" and by_name["03.png"]["overall"] == "pass"
    assert body["passed"] == 2 and body["failed"] == 1


def test_batch_bad_manifest_returns_400(monkeypatch):
    c = client(monkeypatch)
    files = [
        ("images", ("01.png", PNG, "image/png")),
        ("manifest", ("bad.csv", b"brand_name\nOld Tom\n", "text/csv")),
    ]
    r = c.post("/api/verify-batch", files=files)
    assert r.status_code == 400
    assert "Manifest" in r.json()["detail"]
