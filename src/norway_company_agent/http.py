from __future__ import annotations

import json
import hashlib
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .cache import GLOBAL_HTTP_CACHE
from .concurrency import GLOBAL_HOST_GOVERNOR, GLOBAL_REQUEST_TRACKER


@dataclass
class FetchResult:
    url: str
    status: int
    elapsed_ms: int
    bytes_received: int
    body: Any = None
    error: str | None = None
    content_sha256: str | None = None
    retrieved_at: str | None = None
    effective_at: str | None = None
    from_cache: bool = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_json(url: str, *, timeout: float = 20.0, attempts: int = 3, use_cache: bool = True, ttl: float | None = None) -> FetchResult:
    if use_cache:
        cached = GLOBAL_HTTP_CACHE.get(url)
        if cached is not None and isinstance(cached, dict):
            return FetchResult(
                url=cached["url"],
                status=cached["status"],
                elapsed_ms=0,
                bytes_received=0,
                body=cached.get("body"),
                error=cached.get("error"),
                content_sha256=cached.get("content_sha256"),
                retrieved_at=cached.get("retrieved_at"),
                effective_at=cached.get("effective_at"),
                from_cache=True,
            )

    last_error = "request failed"
    for attempt in range(attempts):
        started = time.monotonic()
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "builderr-signalpost-poc/0.1 (+https://builderr.ai)"},
        )
        try:
            with GLOBAL_HOST_GOVERNOR.host_slot(url, timeout=timeout):
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = response.read()
                    elapsed = int((time.monotonic() - started) * 1000)
                    GLOBAL_REQUEST_TRACKER.record_request(url, bytes_received=len(raw), elapsed_ms=elapsed, is_retry=(attempt > 0))
                    res = FetchResult(
                        url,
                        response.status,
                        elapsed,
                        len(raw),
                        json.loads(raw),
                        content_sha256=hashlib.sha256(raw).hexdigest(),
                        retrieved_at=_utc_now(),
                        from_cache=False,
                    )
                    if use_cache:
                        GLOBAL_HTTP_CACHE.set(url, {
                            "url": res.url,
                            "status": res.status,
                            "body": res.body,
                            "error": res.error,
                            "content_sha256": res.content_sha256,
                            "retrieved_at": res.retrieved_at,
                            "effective_at": res.effective_at,
                        }, ttl=ttl)
                    return res
        except urllib.error.HTTPError as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            raw = exc.read()
            GLOBAL_REQUEST_TRACKER.record_request(url, bytes_received=len(raw), elapsed_ms=elapsed, is_retry=(attempt > 0))
            if exc.code in {404, 410}:
                res = FetchResult(
                    url,
                    exc.code,
                    elapsed,
                    len(raw),
                    error=f"HTTP {exc.code}",
                    content_sha256=hashlib.sha256(raw).hexdigest(),
                    retrieved_at=_utc_now(),
                    from_cache=False,
                )
                if use_cache:
                    GLOBAL_HTTP_CACHE.set(url, {
                        "url": res.url,
                        "status": res.status,
                        "body": res.body,
                        "error": res.error,
                        "content_sha256": res.content_sha256,
                        "retrieved_at": res.retrieved_at,
                        "effective_at": res.effective_at,
                    }, ttl=ttl)
                return res
            last_error = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            GLOBAL_REQUEST_TRACKER.record_request(url, bytes_received=0, elapsed_ms=elapsed, is_retry=(attempt > 0))
            last_error = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(0.4 * (2**attempt))
    return FetchResult(url, 0, 0, 0, error=last_error, retrieved_at=_utc_now(), from_cache=False)
