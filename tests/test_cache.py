import threading
import time
import urllib.robotparser
import pytest
from norway_company_agent.cache import HttpCache, RobotsCache, SingleFlight


def test_http_cache_basic():
    cache = HttpCache(default_ttl=10.0)
    assert cache.get("https://example.com/api") is None
    assert cache.misses == 1

    cache.set("https://example.com/api", {"data": 123})
    val = cache.get("https://example.com/api")
    assert val == {"data": 123}
    assert cache.hits == 1
    assert cache.saved_requests == 1


def test_http_cache_expiry():
    cache = HttpCache(default_ttl=0.1)
    cache.set("https://example.com/temp", "fast", ttl=0.05)
    assert cache.get("https://example.com/temp") == "fast"
    time.sleep(0.08)
    assert cache.get("https://example.com/temp") is None


def test_single_flight():
    sf = SingleFlight()
    call_count = 0
    lock = threading.Lock()
    start_gate = threading.Event()

    def work():
        nonlocal call_count
        with lock:
            call_count += 1
        time.sleep(0.1)
        return "result"

    results = []

    def runner():
        start_gate.wait()
        r = sf.do("same-key", work)
        results.append(r)

    threads = [threading.Thread(target=runner) for _ in range(5)]
    for t in threads:
        t.start()
    start_gate.set()
    for t in threads:
        t.join()

    assert len(results) == 5
    assert all(r == "result" for r in results)
    assert call_count == 1  # Only executed once!


def test_robots_cache():
    rc = RobotsCache()
    fetch_count = 0

    def mock_fetch(url):
        nonlocal fetch_count
        fetch_count += 1
        return "User-agent: *\nDisallow: /admin\n"

    # First call - fetches
    allowed = rc.is_allowed("https://example.no/public", "my-bot", mock_fetch)
    assert allowed is True
    assert fetch_count == 1

    # Second call to same domain - uses cache!
    allowed2 = rc.is_allowed("https://example.no/admin", "my-bot", mock_fetch)
    assert allowed2 is False
    assert fetch_count == 1  # Zero additional network fetches!
