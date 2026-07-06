"""Abuse protections: rate limiting, output caps, security headers."""
import app.main as main
from app.extraction.base import ExtractionBackend, LabelExtraction
from app.ratelimit import SlidingWindowLimiter
from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


# ---- limiter unit tests (injected clock) ----
def test_limiter_allows_within_budget():
    t = [0.0]
    lim = SlidingWindowLimiter(limit=10, window_s=60, time_fn=lambda: t[0])
    assert lim.try_acquire("a", 6) is None
    assert lim.try_acquire("a", 4) is None


def test_limiter_blocks_over_budget_then_recovers():
    t = [0.0]
    lim = SlidingWindowLimiter(limit=10, window_s=60, time_fn=lambda: t[0])
    assert lim.try_acquire("a", 10) is None
    retry = lim.try_acquire("a", 1)
    assert retry is not None and retry > 0
    t[0] = 61.0  # window elapsed
    assert lim.try_acquire("a", 10) is None


def test_limiter_keys_are_independent():
    lim = SlidingWindowLimiter(limit=5, window_s=60, time_fn=lambda: 0.0)
    assert lim.try_acquire("a", 5) is None
    assert lim.try_acquire("b", 5) is None  # different client unaffected


def test_limiter_disabled_when_limit_zero():
    lim = SlidingWindowLimiter(limit=0, window_s=60, time_fn=lambda: 0.0)
    assert lim.try_acquire("a", 10_000) is None


# ---- endpoint integration ----
class StubBackend(ExtractionBackend):
    name = "stub"

    def extract(self, image_bytes, content_type):
        return LabelExtraction(readable=False, error="stub")


def test_verify_returns_429_when_limited(monkeypatch):
    monkeypatch.setattr(main, "get_backend", lambda: StubBackend())
    # Exhausted limiter: everything is over budget.
    exhausted = SlidingWindowLimiter(limit=1, window_s=600, time_fn=lambda: 0.0)
    exhausted.try_acquire("testclient", 1)
    monkeypatch.setattr("app.ratelimit._limiter", exhausted)

    c = TestClient(main.app)
    r = c.post("/api/verify", data={"mode": "rules"},
               files={"image": ("x.png", PNG, "image/png")})
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_security_and_cache_headers(monkeypatch):
    monkeypatch.setattr(main, "get_backend", lambda: StubBackend())
    c = TestClient(main.app)
    api = c.get("/api/health")
    assert api.headers["X-Content-Type-Options"] == "nosniff"
    assert "Cache-Control" not in api.headers or "no-cache" not in api.headers.get("Cache-Control", "")
    page = c.get("/")
    assert page.headers.get("Cache-Control") == "no-cache"


# ---- extraction output caps ----
def test_extraction_fields_are_length_capped():
    from app.extraction.claude_backend import _clean

    assert len(_clean("x" * 50_000)) == 1000
    assert _clean(None) is None
    assert _clean("   ") is None
