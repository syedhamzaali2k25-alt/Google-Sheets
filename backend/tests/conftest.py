import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """app.main's rate limiter is a process-lifetime singleton shared by
    every request the FastAPI app handles. Without this, tests that hit the
    real app via TestClient would accumulate rate-limit state across
    unrelated test files (they all share Starlette TestClient's fixed
    "testclient" client host) and could start failing with spurious 429s
    depending on test order — reset it before every test so each one gets
    a full budget regardless of what ran before it."""
    import app.main as main_module

    main_module.rate_limiter.reset()
    yield
