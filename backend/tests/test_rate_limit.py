import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.rate_limit import RateLimiter, RateLimitMiddleware


def test_allows_requests_up_to_burst_capacity():
    limiter = RateLimiter(requests_per_minute=60, burst=3)
    results = [limiter.allow("client-a", now=0.0)[0] for _ in range(3)]
    assert results == [True, True, True]


def test_rejects_once_burst_is_exhausted():
    limiter = RateLimiter(requests_per_minute=60, burst=3)
    for _ in range(3):
        limiter.allow("client-a", now=0.0)
    allowed, retry_after = limiter.allow("client-a", now=0.0)
    assert allowed is False
    assert retry_after > 0


def test_tokens_refill_over_time():
    limiter = RateLimiter(requests_per_minute=60, burst=1)  # 1 token/sec refill
    limiter.allow("client-a", now=0.0)
    assert limiter.allow("client-a", now=0.5)[0] is False  # not refilled yet
    assert limiter.allow("client-a", now=1.1)[0] is True  # refilled after ~1s


def test_different_keys_have_independent_budgets():
    limiter = RateLimiter(requests_per_minute=60, burst=1)
    assert limiter.allow("client-a", now=0.0)[0] is True
    assert limiter.allow("client-b", now=0.0)[0] is True
    assert limiter.allow("client-a", now=0.0)[0] is False


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        RateLimiter(requests_per_minute=0, burst=10)
    with pytest.raises(ValueError):
        RateLimiter(requests_per_minute=10, burst=0)


def test_reset_clears_all_buckets():
    limiter = RateLimiter(requests_per_minute=60, burst=1)
    limiter.allow("client-a", now=0.0)
    assert limiter.allow("client-a", now=0.0)[0] is False  # exhausted

    limiter.reset()
    assert limiter.allow("client-a", now=0.0)[0] is True  # back to a full budget


def test_bucket_eviction_caps_tracked_keys():
    limiter = RateLimiter(requests_per_minute=60, burst=1, max_tracked_keys=2)
    limiter.allow("a", now=0.0)
    limiter.allow("b", now=0.0)
    limiter.allow("c", now=0.0)  # evicts "a"
    # "a" should be treated as brand-new again (full bucket), not still-exhausted
    assert limiter.allow("a", now=0.0)[0] is True


# --- Middleware-level behavior -------------------------------------------


def _build_app(limiter: RateLimiter) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/sheets/x")
    def sheets():
        return {"ok": True}

    return app


def test_health_endpoint_is_exempt_from_rate_limiting():
    limiter = RateLimiter(requests_per_minute=60, burst=1)
    client = TestClient(_build_app(limiter))

    for _ in range(5):
        response = client.get("/health")
        assert response.status_code == 200


def test_other_endpoints_get_429_after_burst_with_retry_after_header():
    limiter = RateLimiter(requests_per_minute=60, burst=1)
    client = TestClient(_build_app(limiter))

    first = client.get("/sheets/x")
    second = client.get("/sheets/x")

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers
    assert second.json()["detail"]


def test_rate_limit_response_still_carries_cors_headers():
    """CORS must stay the outermost middleware (see main.py) so a 429 from
    the rate limiter still gets CORS headers instead of the browser
    reporting a confusing CORS failure over the real error."""
    from starlette.middleware.cors import CORSMiddleware

    limiter = RateLimiter(requests_per_minute=60, burst=1)
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    app.add_middleware(CORSMiddleware, allow_origins=["https://example.com"], allow_credentials=True)

    @app.get("/sheets/x")
    def sheets():
        return {"ok": True}

    client = TestClient(app)
    client.get("/sheets/x", headers={"Origin": "https://example.com"})
    limited = client.get("/sheets/x", headers={"Origin": "https://example.com"})

    assert limited.status_code == 429
    assert limited.headers.get("access-control-allow-origin") == "https://example.com"
