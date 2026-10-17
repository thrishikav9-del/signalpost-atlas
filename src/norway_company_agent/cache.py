"""
Signalpost Atlas — Thread-Safe Caching & Single-Flight Deduplication Subsystem.

Features:
- Thread-safe HTTP response cache with configurable TTL and persistent storage option.
- Single-flight deduplication preventing duplicate in-flight requests to identical URLs.
- Domain-level robots.txt caching to eliminate redundant robots.txt network fetches.
- Explicit metrics tracking for cache hits, misses, saved network requests, and saved bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class CacheEntry:
    value: Any
    created_at: float
    expires_at: float
    content_sha256: str | None = None
    headers: dict[str, str] | None = None


class _Call:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: Any = None
        self.error: Exception | None = None


class SingleFlight:
    """Ensures concurrent calls for the same key execute only once."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: dict[str, _Call] = {}

    def do(self, key: str, fn: Callable[[], Any]) -> Any:
        with self._lock:
            if key in self._calls:
                call = self._calls[key]
                execute = False
            else:
                call = _Call()
                self._calls[key] = call
                execute = True

        if not execute:
            call.event.wait()
            if call.error is not None:
                raise call.error
            return call.result

        try:
            call.result = fn()
            return call.result
        except Exception as exc:
            call.error = exc
            raise
        finally:
            call.event.set()
            with self._lock:
                self._calls.pop(key, None)


class HttpCache:
    """Thread-safe in-memory and disk-backed HTTP cache."""

    def __init__(self, disk_dir: Path | None = None, default_ttl: float = 3600.0) -> None:
        self.disk_dir = disk_dir
        self.default_ttl = default_ttl
        self._lock = threading.Lock()
        self._memory: dict[str, CacheEntry] = {}
        self._single_flight = SingleFlight()
        self.hits: int = 0
        self.misses: int = 0
        self.saved_requests: int = 0
        self.saved_bytes: int = 0

        if self.disk_dir:
            self.disk_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key_for_url(url: str, headers: dict[str, str] | None = None) -> str:
        payload = url.strip()
        if headers:
            sorted_headers = sorted(f"{k.lower()}:{v}" for k, v in headers.items())
            payload += "||" + "|".join(sorted_headers)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, url: str, headers: dict[str, str] | None = None) -> Any | None:
        key = self.key_for_url(url, headers)
        now = time.monotonic()

        with self._lock:
            entry = self._memory.get(key)
            if entry is not None:
                if entry.expires_at > now:
                    self.hits += 1
                    self.saved_requests += 1
                    return entry.value
                else:
                    self._memory.pop(key, None)

        # Check disk cache if configured
        if self.disk_dir:
            disk_file = self.disk_dir / f"{key}.json"
            if disk_file.exists():
                try:
                    data = json.loads(disk_file.read_text(encoding="utf-8"))
                    if data.get("expires_at", 0) > time.time():
                        with self._lock:
                            self.hits += 1
                            self.saved_requests += 1
                            self._memory[key] = CacheEntry(
                                value=data["value"],
                                created_at=now,
                                expires_at=now + (data["expires_at"] - time.time()),
                            )
                        return data["value"]
                    else:
                        disk_file.unlink(missing_ok=True)
                except Exception:
                    pass

        with self._lock:
            self.misses += 1
        return None

    def set(self, url: str, value: Any, ttl: float | None = None, headers: dict[str, str] | None = None) -> None:
        key = self.key_for_url(url, headers)
        effective_ttl = ttl if ttl is not None else self.default_ttl
        now = time.monotonic()
        entry = CacheEntry(
            value=value,
            created_at=now,
            expires_at=now + effective_ttl,
        )

        with self._lock:
            self._memory[key] = entry

        if self.disk_dir:
            try:
                disk_file = self.disk_dir / f"{key}.json"
                disk_file.write_text(
                    json.dumps({
                        "url": url,
                        "value": value,
                        "created_at": time.time(),
                        "expires_at": time.time() + effective_ttl,
                    }, ensure_ascii=False),
                    encoding="utf-8"
                )
            except Exception:
                pass

    def get_or_fetch(self, url: str, fetch_fn: Callable[[], Any], ttl: float | None = None, headers: dict[str, str] | None = None) -> tuple[Any, bool]:
        """Returns (result, was_cache_hit). Uses single-flight deduplication."""
        cached = self.get(url, headers)
        if cached is not None:
            return cached, True

        key = self.key_for_url(url, headers)

        def _execute() -> Any:
            # Re-check inside single-flight to handle queued waiters
            inner = self.get(url, headers)
            if inner is not None:
                return inner
            result = fetch_fn()
            self.set(url, result, ttl, headers)
            return result

        result = self._single_flight.do(key, _execute)
        return result, False

    def clear(self) -> None:
        with self._lock:
            self._memory.clear()
            self.hits = 0
            self.misses = 0
            self.saved_requests = 0
            self.saved_bytes = 0

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            hit_ratio = (self.hits / total) if total > 0 else 0.0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "total": total,
                "hit_ratio": round(hit_ratio, 4),
                "saved_requests": self.saved_requests,
                "saved_bytes": self.saved_bytes,
                "cached_items": len(self._memory),
            }


class RobotsCache:
    """Domain-level robots.txt cache with thread safety."""

    def __init__(self, default_ttl: float = 86400.0) -> None:
        self.default_ttl = default_ttl
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, urllib.robotparser.RobotFileParser]] = {}
        self._single_flight = SingleFlight()

    @staticmethod
    def domain_key(url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}".lower()

    def get_parser(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        key = self.domain_key(url)
        now = time.monotonic()
        with self._lock:
            item = self._cache.get(key)
            if item:
                exp, parser = item
                if exp > now:
                    return parser
                else:
                    self._cache.pop(key, None)
        return None

    def set_parser(self, url: str, parser: urllib.robotparser.RobotFileParser, ttl: float | None = None) -> None:
        key = self.domain_key(url)
        effective_ttl = ttl if ttl is not None else self.default_ttl
        now = time.monotonic()
        with self._lock:
            self._cache[key] = (now + effective_ttl, parser)

    def is_allowed(self, url: str, user_agent: str, fetch_raw_robots_fn: Callable[[str], str | None]) -> bool:
        parser = self.get_parser(url)
        if parser is not None:
            return parser.can_fetch(user_agent, url)

        key = self.domain_key(url)

        def _load_and_parse() -> urllib.robotparser.RobotFileParser:
            existing = self.get_parser(url)
            if existing is not None:
                return existing
            parsed = urllib.parse.urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            p = urllib.robotparser.RobotFileParser()
            p.set_url(robots_url)
            raw = fetch_raw_robots_fn(robots_url)
            if raw is not None:
                p.parse(raw.splitlines())
            else:
                # Default allow if robots.txt absent or failed
                p.allow_all = True
            self.set_parser(url, p)
            return p

        parser = self._single_flight.do(key, _load_and_parse)
        return parser.can_fetch(user_agent, url)


# Shared global instances for the process
GLOBAL_HTTP_CACHE = HttpCache()
GLOBAL_ROBOTS_CACHE = RobotsCache()
