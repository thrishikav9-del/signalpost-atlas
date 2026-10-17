"""
Signalpost Atlas — Concurrency, Host Throttling and Operational Watchdog
Enforces:
1. Configurable global worker limits.
2. Strict per-hostname concurrency ceiling (maximum 2 concurrent requests per host).
3. Centralized, thread-safe request counting across all workers, retries and redirects.
4. Watchdog budget enforcement (wall-clock deadline and request ceiling).
5. Dynamic module shedding governor with structured audit event logging.
"""
from __future__ import annotations

import os
import re
import threading
import time
import urllib.parse
from contextlib import contextmanager
from typing import Any, Callable


def _extract_host(url_or_host: str) -> str:
    parsed = urllib.parse.urlparse(url_or_host)
    host = parsed.hostname or url_or_host
    return host.lower().strip().removeprefix("www.")


class HostConcurrencyGovernor:
    """Limits concurrent outbound HTTP requests per hostname.
    Enforces a strict upper ceiling of at most 2 concurrent requests per host.
    """

    def __init__(self, max_per_host: int = 2):
        # Strict requirement: never allow more than two concurrent requests to one hostname
        int_val = int(max_per_host)
        if int_val > 2:
            import warnings
            warnings.warn(f"Requested max_per_host={int_val} exceeds safe ceiling of 2; clamped to 2.", UserWarning)
        self.max_per_host = max(1, min(int_val, 2))
        self._semaphores: dict[str, threading.Semaphore] = {}
        self._active_counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def set_max_per_host(self, max_per_host: int) -> None:
        with self._lock:
            int_val = int(max_per_host)
            if int_val > 2:
                import warnings
                warnings.warn(f"Requested max_per_host={int_val} exceeds safe ceiling of 2; clamped to 2.", UserWarning)
            self.max_per_host = max(1, min(int_val, 2))
            self._semaphores.clear()
            self._active_counts.clear()

    @contextmanager
    def host_slot(self, url_or_host: str, timeout: float = 30.0):
        host = _extract_host(url_or_host)
        with self._lock:
            if host not in self._semaphores:
                self._semaphores[host] = threading.Semaphore(self.max_per_host)
                self._active_counts[host] = 0
            sem = self._semaphores[host]

        acquired = sem.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(f"Concurrency slot acquisition timed out after {timeout}s for host: {host}")

        with self._lock:
            self._active_counts[host] = self._active_counts.get(host, 0) + 1

        try:
            yield
        finally:
            with self._lock:
                self._active_counts[host] = max(0, self._active_counts.get(host, 1) - 1)
            sem.release()

    def active_requests_for_host(self, url_or_host: str) -> int:
        host = _extract_host(url_or_host)
        with self._lock:
            return self._active_counts.get(host, 0)


class CentralizedRequestTracker:
    """Thread-safe central counter for all outbound HTTP requests."""

    def __init__(self):
        self._count = 0
        self._bytes = 0
        self._retries = 0
        self._redirects = 0
        self._host_requests: dict[str, int] = {}
        self._latencies_ms: list[int] = []
        self._lock = threading.Lock()

    def record_request(self, url: str, bytes_received: int = 0, elapsed_ms: int = 0, is_retry: bool = False, is_redirect: bool = False) -> int:
        host = _extract_host(url)
        with self._lock:
            self._count += 1
            self._bytes += bytes_received
            if elapsed_ms > 0:
                self._latencies_ms.append(elapsed_ms)
            if is_retry:
                self._retries += 1
            if is_redirect:
                self._redirects += 1
            self._host_requests[host] = self._host_requests.get(host, 0) + 1
            return self._count

    def reset(self) -> None:
        with self._lock:
            self._count = 0
            self._bytes = 0
            self._retries = 0
            self._redirects = 0
            self._host_requests.clear()
            self._latencies_ms.clear()

    @property
    def total_requests(self) -> int:
        with self._lock:
            return self._count

    @property
    def total_bytes(self) -> int:
        with self._lock:
            return self._bytes

    @property
    def total_retries(self) -> int:
        with self._lock:
            return self._retries

    @property
    def total_redirects(self) -> int:
        with self._lock:
            return self._redirects

    def summary(self) -> dict[str, Any]:
        with self._lock:
            lat = sorted(self._latencies_ms)
            p50 = lat[len(lat) // 2] if lat else 0
            p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else 0
            return {
                "total_requests": self._count,
                "total_bytes": self._bytes,
                "total_retries": self._retries,
                "total_redirects": self._redirects,
                "p50_latency_ms": p50,
                "p95_latency_ms": p95,
                "unique_hosts": len(self._host_requests),
                "host_breakdown": dict(self._host_requests),
            }


class OperationalWatchdog:
    """Monitors batch runtime deadline and request budget."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 2700.0,
        shutdown_margin: float = 30.0,
        max_requests: int = 2000,
        tracker: CentralizedRequestTracker | None = None,
    ):
        self.timeout_seconds = float(timeout_seconds)
        self.shutdown_margin = float(shutdown_margin)
        self.max_requests = int(max_requests)
        self.tracker = tracker or GLOBAL_REQUEST_TRACKER
        self.start_monotonic = time.monotonic()
        self._events: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def reset(
        self,
        *,
        timeout_seconds: float | None = None,
        shutdown_margin: float | None = None,
        max_requests: int | None = None,
    ) -> None:
        with self._lock:
            if timeout_seconds is not None:
                self.timeout_seconds = float(timeout_seconds)
            if shutdown_margin is not None:
                self.shutdown_margin = float(shutdown_margin)
            if max_requests is not None:
                self.max_requests = int(max_requests)
            self.start_monotonic = time.monotonic()
            self._events.clear()

    def record_event(self, event_type: str, details: dict[str, Any]) -> None:
        with self._lock:
            self._events.append({
                "timestamp_ms": int((time.monotonic() - self.start_monotonic) * 1000),
                "event_type": event_type,
                "details": details,
            })

    def check_governor(self, remaining_companies: int, active_modules: set[str]) -> tuple[set[str], bool]:
        """Dynamically shed optional modules to protect deadline and request allowance."""
        now = time.monotonic()
        elapsed = now - self.start_monotonic
        remaining_time = self.timeout_seconds - elapsed
        curr_requests = self.tracker.total_requests

        # Emergency wind-down
        if remaining_time <= self.shutdown_margin or curr_requests >= self.max_requests - 10:
            self.record_event("emergency_wind_down", {
                "remaining_time": round(remaining_time, 2),
                "curr_requests": curr_requests,
                "max_requests": self.max_requests,
            })
            return set(), True

        req_left = max(0, self.max_requests - curr_requests)
        rem_co = max(1, remaining_companies)
        allowance = req_left / rem_co

        filtered = set(active_modules)
        if allowance < 3.0:
            omitted = filtered & {"group", "roles", "locations"}
            if omitted:
                filtered -= {"group", "roles", "locations"}
                self.record_event("throttle_tertiary_modules", {
                    "allowance_per_co": round(allowance, 2),
                    "omitted_modules": sorted(omitted),
                    "remaining_companies": rem_co,
                })
        elif allowance < 4.0:
            omitted = filtered & {"group"}
            if omitted:
                filtered -= {"group"}
                self.record_event("throttle_group_module", {
                    "allowance_per_co": round(allowance, 2),
                    "omitted_modules": sorted(omitted),
                    "remaining_companies": rem_co,
                })

        return filtered, False

    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)


# Global default instances
GLOBAL_HOST_GOVERNOR = HostConcurrencyGovernor(max_per_host=2)
GLOBAL_REQUEST_TRACKER = CentralizedRequestTracker()
GLOBAL_WATCHDOG = OperationalWatchdog(tracker=GLOBAL_REQUEST_TRACKER)


def resolve_operational_config(cli_args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolves operational settings in order of precedence:
    CLI flag > Environment variable > Safe default.
    Enforces safety bounds (e.g. max_per_host <= 2).
    """
    args = cli_args or {}

    # Definitions: key: (type, default_val, env_var_name, max_bound, min_bound)
    specs = {
        "workers": (int, 6, "SIGNALPOST_WORKERS", 64, 1),
        "max_per_host": (int, 2, "SIGNALPOST_MAX_PER_HOST", 2, 1),
        "max_requests": (int, 2000, "SIGNALPOST_MAX_REQUESTS", 100000, 1),
        "timeout_seconds": (float, 2700.0, "SIGNALPOST_TIMEOUT_SECONDS", 86400.0, 1.0),
        "shutdown_margin": (float, 30.0, "SIGNALPOST_SHUTDOWN_MARGIN", 3600.0, 0.0),
        "per_request_timeout": (float, 8.0, "SIGNALPOST_PER_REQUEST_TIMEOUT", 120.0, 0.5),
    }

    resolved = {}
    for key, (val_type, default_val, env_var, max_b, min_b) in specs.items():
        cli_val = args.get(key)
        env_val = os.environ.get(env_var)

        source = "default"
        raw_val = default_val

        if cli_val is not None:
            raw_val = cli_val
            source = "cli"
        elif env_val is not None and env_val.strip():
            raw_val = env_val.strip()
            source = f"env:{env_var}"

        try:
            converted = val_type(raw_val)
        except (ValueError, TypeError):
            converted = default_val
            source = f"default (fallback from invalid {raw_val!r})"

        effective = max(min_b, min(converted, max_b))
        clamped = effective != converted

        resolved[key] = {
            "requested": converted,
            "effective": effective,
            "source": source,
            "clamped": clamped,
            "ceiling": max_b,
        }

    return resolved


def format_config_table(config: dict[str, Any]) -> str:
    """Formats a structured table of effective configuration settings."""
    lines = [
        "================================================================================",
        "SIGNALPOST ATLAS — OPERATIONAL CONFIGURATION",
        "--------------------------------------------------------------------------------",
        f"{'Setting':<24} | {'Effective':<12} | {'Requested':<12} | {'Source':<20} | {'Status'}",
        "--------------------------------------------------------------------------------",
    ]
    for key, data in config.items():
        eff = str(data["effective"])
        req = str(data["requested"])
        src = str(data["source"])
        status = "CLAMPED (<= 2 ceiling)" if (key == "max_per_host" and data["clamped"]) else ("CLAMPED" if data["clamped"] else "OK")
        lines.append(f"{key:<24} | {eff:<12} | {req:<12} | {src:<20} | {status}")
    lines.append("================================================================================")
    return "\n".join(lines)


def apply_operational_config(config: dict[str, Any]) -> None:
    """Applies resolved operational configuration to global singletons."""
    if "max_per_host" in config:
        GLOBAL_HOST_GOVERNOR.set_max_per_host(config["max_per_host"]["effective"])

    if "max_requests" in config or "timeout_seconds" in config or "shutdown_margin" in config:
        GLOBAL_WATCHDOG.reset(
            timeout_seconds=config.get("timeout_seconds", {}).get("effective"),
            shutdown_margin=config.get("shutdown_margin", {}).get("effective"),
            max_requests=config.get("max_requests", {}).get("effective"),
        )

