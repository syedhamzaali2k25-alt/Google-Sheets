from app.cache import RevisionCache, token_fingerprint


def test_token_fingerprint_is_stable_and_one_way():
    fingerprint = token_fingerprint("secret-token")
    assert fingerprint == token_fingerprint("secret-token")
    assert "secret-token" not in fingerprint
    assert len(fingerprint) == 16


def test_token_fingerprint_differs_for_different_tokens():
    assert token_fingerprint("token-a") != token_fingerprint("token-b")


def test_set_then_get_with_matching_revision():
    cache = RevisionCache(ttl_seconds=60)
    cache.set("key", {"data": 1}, revision="rev-1")
    assert cache.get("key", revision="rev-1") == {"data": 1}


def test_get_with_different_revision_is_a_miss():
    cache = RevisionCache(ttl_seconds=60)
    cache.set("key", {"data": 1}, revision="rev-1")
    assert cache.get("key", revision="rev-2") is None


def test_get_without_revision_check_ignores_stored_revision():
    cache = RevisionCache(ttl_seconds=60)
    cache.set("key", {"data": 1}, revision="rev-1")
    assert cache.get("key") == {"data": 1}


def test_missing_key_is_a_miss():
    cache = RevisionCache(ttl_seconds=60)
    assert cache.get("nope") is None


def test_ttl_expiry(monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr("app.cache.time.monotonic", lambda: fake_now[0])

    cache = RevisionCache(ttl_seconds=10)
    cache.set("key", "value")
    assert cache.get("key") == "value"

    fake_now[0] += 11
    assert cache.get("key") is None


def test_clear_removes_everything():
    cache = RevisionCache(ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_eviction_caps_store_size(monkeypatch):
    monkeypatch.setattr("app.cache._MAX_ENTRIES", 3)
    cache = RevisionCache(ttl_seconds=60)
    for i in range(5):
        cache.set(f"key-{i}", i)

    remaining = [cache.get(f"key-{i}") for i in range(5)]
    assert remaining.count(None) == 2
    assert remaining[-1] == 4  # the most recently set key is never evicted
