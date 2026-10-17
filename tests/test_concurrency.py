"""
Signalpost Atlas — Concurrency & Operational Watchdog Regression Tests
Verifies the 10 Phase C requirements:
1. Worker pool processes tasks concurrently up to configured limit.
2. Per-host semaphore strictly enforces <= 2 concurrent requests to the same host.
3. Requests to distinct hosts proceed concurrently without blocking each other.
4. Centralized request tracker accurately counts requests across threads without race conditions.
5. Retries and redirects are counted in total outbound requests.
6. Watchdog triggers module shedding when request allowance per company falls below threshold.
7. Watchdog triggers emergency wind-down when deadline or request ceiling is reached.
8. Timeout on slow host does not hang the worker pool.
9. Invalid per-host concurrency configuration (>2) is safely clamped to 2.
10. Atomic checkpointing is thread-safe and preserves valid JSONL.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from norway_company_agent.concurrency import (
    CentralizedRequestTracker,
    HostConcurrencyGovernor,
    OperationalWatchdog,
    resolve_operational_config,
)
from scripts.run_competition_batch import write_jsonl


class ConcurrencyAndWatchdogTests(unittest.TestCase):
    # Test 1: Worker pool processes tasks concurrently up to configured limit
    def test_1_worker_pool_concurrency_limit(self):
        max_workers = 4
        active_workers = 0
        peak_active = 0
        lock = threading.Lock()

        def worker_task():
            nonlocal active_workers, peak_active
            with lock:
                active_workers += 1
                if active_workers > peak_active:
                    peak_active = active_workers
            time.sleep(0.05)
            with lock:
                active_workers -= 1
            return True

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(worker_task) for _ in range(12)]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 12)
        self.assertTrue(all(results))
        self.assertGreater(peak_active, 1)
        self.assertLessEqual(peak_active, max_workers)

    # Test 2: Per-host semaphore strictly enforces <= 2 concurrent requests to the same host
    def test_2_per_host_semaphore_enforces_max_2_concurrency(self):
        governor = HostConcurrencyGovernor(max_per_host=2)
        target_host = "https://data.brreg.no/enhetsregisteret/api/enheter"
        active_count = 0
        max_observed_active = 0
        lock = threading.Lock()

        def probe():
            nonlocal active_count, max_observed_active
            with governor.host_slot(target_host, timeout=5.0):
                with lock:
                    active_count += 1
                    if active_count > max_observed_active:
                        max_observed_active = active_count
                time.sleep(0.04)
                with lock:
                    active_count -= 1
            return True

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(probe) for _ in range(6)]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 6)
        self.assertTrue(all(results))
        self.assertLessEqual(max_observed_active, 2)
        self.assertGreaterEqual(max_observed_active, 1)

    # Test 3: Requests to distinct hosts proceed concurrently without blocking each other
    def test_3_distinct_hosts_proceed_concurrently(self):
        governor = HostConcurrencyGovernor(max_per_host=2)
        barrier = threading.Barrier(4)
        acquired_simultaneously = False

        def slot_task(url: str):
            nonlocal acquired_simultaneously
            with governor.host_slot(url, timeout=5.0):
                # If all 4 tasks can wait at the barrier together, they are all concurrently active!
                try:
                    barrier.wait(timeout=1.0)
                    acquired_simultaneously = True
                except threading.BrokenBarrierError:
                    pass

        threads = [
            threading.Thread(target=slot_task, args=("https://host1.no",)),
            threading.Thread(target=slot_task, args=("https://host1.no",)),
            threading.Thread(target=slot_task, args=("https://host2.com",)),
            threading.Thread(target=slot_task, args=("https://host2.com",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertTrue(acquired_simultaneously)

    # Test 4: Centralized request tracker accurately counts requests across threads without race conditions
    def test_4_centralized_request_tracker_thread_safety(self):
        tracker = CentralizedRequestTracker()
        threads_count = 8
        requests_per_thread = 50

        def spam_tracker(thread_idx: int):
            for i in range(requests_per_thread):
                host = f"https://api{thread_idx % 3}.test/res"
                tracker.record_request(host, bytes_received=100, elapsed_ms=10)

        threads = [threading.Thread(target=spam_tracker, args=(i,)) for i in range(threads_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected_total = threads_count * requests_per_thread
        self.assertEqual(tracker.total_requests, expected_total)
        self.assertEqual(tracker.total_bytes, expected_total * 100)
        summary = tracker.summary()
        self.assertEqual(summary["total_requests"], expected_total)
        self.assertEqual(summary["unique_hosts"], 3)
        self.assertEqual(sum(summary["host_breakdown"].values()), expected_total)

    # Test 5: Retries and redirects are counted in total outbound requests
    def test_5_retries_and_redirects_counted_in_total_outbound(self):
        tracker = CentralizedRequestTracker()
        tracker.record_request("https://test.no/a", bytes_received=500, elapsed_ms=20)
        tracker.record_request("https://test.no/a", bytes_received=500, elapsed_ms=25, is_retry=True)
        tracker.record_request("https://test.no/b", bytes_received=0, elapsed_ms=5, is_redirect=True)
        tracker.record_request("https://test.no/c", bytes_received=1000, elapsed_ms=30)

        self.assertEqual(tracker.total_requests, 4)
        self.assertEqual(tracker.total_retries, 1)
        self.assertEqual(tracker.total_redirects, 1)
        self.assertEqual(tracker.total_bytes, 2000)

    # Test 6: Watchdog triggers module shedding when request allowance per company falls below threshold
    def test_6_watchdog_triggers_module_shedding_when_allowance_drops(self):
        tracker = CentralizedRequestTracker()
        # Set max_requests=100
        watchdog = OperationalWatchdog(max_requests=100, tracker=tracker)
        active_modules = {"registry", "financials", "roles", "group", "locations"}

        # Simulate 50 requests used, 20 companies remaining -> allowance = (100 - 50)/20 = 2.5 (< 3.0)
        for _ in range(50):
            tracker.record_request("https://test.com")

        filtered, wind_down = watchdog.check_governor(20, active_modules)
        self.assertFalse(wind_down)
        self.assertEqual(filtered, {"registry", "financials"})  # group, roles, locations shed
        events = watchdog.events()
        self.assertTrue(any(e["event_type"] == "throttle_tertiary_modules" for e in events))

        # Reset and test allowance < 4.0: (100 - 30)/20 = 3.5
        tracker.reset()
        watchdog.reset()
        for _ in range(30):
            tracker.record_request("https://test.com")

        filtered2, wind_down2 = watchdog.check_governor(20, active_modules)
        self.assertFalse(wind_down2)
        self.assertEqual(filtered2, {"registry", "financials", "roles", "locations"})  # group shed
        events2 = watchdog.events()
        self.assertTrue(any(e["event_type"] == "throttle_group_module" for e in events2))

    # Test 7: Watchdog triggers emergency wind-down when deadline or request ceiling is reached
    def test_7_watchdog_triggers_emergency_wind_down(self):
        tracker = CentralizedRequestTracker()
        watchdog = OperationalWatchdog(max_requests=100, timeout_seconds=60.0, shutdown_margin=30.0, tracker=tracker)
        active_modules = {"registry", "financials"}

        # Ceiling condition: curr_requests >= max_requests - 10 (>= 90)
        for _ in range(92):
            tracker.record_request("https://test.com")

        filtered, wind_down = watchdog.check_governor(10, active_modules)
        self.assertTrue(wind_down)
        self.assertEqual(filtered, set())
        events = watchdog.events()
        self.assertTrue(any(e["event_type"] == "emergency_wind_down" for e in events))

        # Deadline condition: remaining time <= shutdown_margin
        tracker.reset()
        watchdog.reset(timeout_seconds=20.0, shutdown_margin=30.0)  # already within margin
        filtered_time, wind_down_time = watchdog.check_governor(10, active_modules)
        self.assertTrue(wind_down_time)
        self.assertEqual(filtered_time, set())

    # Test 8: Timeout on slow host does not hang the worker pool
    def test_8_timeout_on_slow_host_does_not_hang_worker_pool(self):
        governor = HostConcurrencyGovernor(max_per_host=1)

        # Acquire the single slot and hold it
        def hold_slot():
            with governor.host_slot("https://slowhost.com", timeout=1.0):
                time.sleep(0.2)

        t = threading.Thread(target=hold_slot)
        t.start()
        time.sleep(0.02)  # ensure t has acquired the slot

        # Attempt to acquire with very short timeout (0.05s) -> must raise TimeoutError quickly
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            with governor.host_slot("https://slowhost.com", timeout=0.05):
                pass
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.15)
        t.join()

    # Test 9: Invalid per-host concurrency configuration (>2) is safely clamped to 2
    def test_9_invalid_per_host_concurrency_clamped_to_2(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            gov = HostConcurrencyGovernor(max_per_host=10)
            self.assertEqual(gov.max_per_host, 2)
            self.assertTrue(any("exceeds safe ceiling of 2" in str(item.message) for item in w))

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            gov.set_max_per_host(8)
            self.assertEqual(gov.max_per_host, 2)

        config = resolve_operational_config({"max_per_host": 5})
        self.assertEqual(config["max_per_host"]["effective"], 2)
        self.assertEqual(config["max_per_host"]["requested"], 5)
        self.assertTrue(config["max_per_host"]["clamped"])

    # Test 10: Atomic checkpointing is thread-safe and preserves valid JSONL
    def test_10_atomic_checkpointing_thread_safe_preserves_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "checkpoint.jsonl"

            def writer_task(batch_idx: int):
                rows = [{"batch": batch_idx, "item": i, "val": f"data_{i}"} for i in range(10)]
                write_jsonl(test_file, rows)

            threads = [threading.Thread(target=writer_task, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertTrue(test_file.exists())
            lines = test_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 10)
            for line in lines:
                parsed = json.loads(line)
                self.assertIn("batch", parsed)
                self.assertIn("item", parsed)


if __name__ == "__main__":
    unittest.main()
