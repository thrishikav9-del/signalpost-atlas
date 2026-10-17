"""
Signalpost Atlas — Progressive Benchmark Runner (Phase D)
Executes structured benchmarks for 10 and 50 companies across worker counts.
Extracts metrics and formats markdown tables.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = sys.executable


def run_single_benchmark(
    *,
    dataset_path: Path,
    expected_count: int,
    workers: int,
    run_id: str,
    output_dir: Path,
    skip_existing: bool = True,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    envelopes_file = output_dir / "envelopes.jsonl"
    profiles_file = output_dir / "profiles.jsonl"
    report_file = output_dir / "report.json"

    if skip_existing and report_file.exists() and envelopes_file.exists() and profiles_file.exists():
        try:
            report_data = json.loads(report_file.read_text(encoding="utf-8"))
            if report_data.get("emitted_envelopes") == expected_count:
                print(f"\n>>> Reusing existing completed benchmark {run_id} ({expected_count} orgs, {workers} workers)...")
                elapsed_wall = report_data.get("watchdog", {}).get("elapsed_seconds", 0.0)
                return _parse_benchmark_metrics(run_id, expected_count, workers, elapsed_wall, envelopes_file, profiles_file, report_file)
        except Exception:
            pass

    cmd = [
        PYTHON_EXE,
        str(ROOT / "scripts" / "run_competition_batch.py"),
        "--organisations", str(dataset_path),
        "--expected-count", str(expected_count),
        "--workers", str(workers),
        "--run-id", run_id,
        "--output", str(envelopes_file),
        "--profiles-output", str(profiles_file),
        "--report", str(report_file),
    ]

    print(f"\n>>> Running benchmark {run_id}: {expected_count} orgs, {workers} workers...")
    t0 = time.monotonic()
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    t1 = time.monotonic()
    elapsed_wall = round(t1 - t0, 3)

    if proc.returncode != 0:
        print(f"FAILED (exit {proc.returncode})")
        print("STDERR:\n", (proc.stderr or "")[-1000:])
        print("STDOUT:\n", (proc.stdout or "")[-1000:])
        raise RuntimeError(f"Benchmark {run_id} failed with exit code {proc.returncode}")

    return _parse_benchmark_metrics(run_id, expected_count, workers, elapsed_wall, envelopes_file, profiles_file, report_file)


def _parse_benchmark_metrics(
    run_id: str,
    expected_count: int,
    workers: int,
    elapsed_wall: float,
    envelopes_file: Path,
    profiles_file: Path,
    report_file: Path,
) -> dict:
    report = json.loads(report_file.read_text(encoding="utf-8"))
    envelopes = [json.loads(line) for line in envelopes_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    profiles = [json.loads(line) for line in profiles_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    total_claims = sum(len(e.get("claims", [])) for e in envelopes)
    claims_per_co = round(total_claims / len(envelopes), 2) if envelopes else 0.0

    total_evidence = sum(len(p.get("evidence", {})) for p in profiles)
    evidence_per_co = round(total_evidence / len(profiles), 2) if profiles else 0.0

    # Website statuses
    website_statuses = {"available": 0, "ambiguous": 0, "blocked": 0, "not_available": 0}
    for e in envelopes:
        for c in e.get("claims", []):
            if c.get("field") == "official_website":
                avail = c.get("availability")
                if avail in website_statuses:
                    website_statuses[avail] += 1
                else:
                    website_statuses[avail] = 1

    ops = report.get("operations", {})
    tracker_summary = ops.get("tracker_summary", {})
    total_requests = tracker_summary.get("total_requests", ops.get("requests", 0))
    p50_ms = tracker_summary.get("p50_latency_ms", ops.get("p50_ms", 0))
    p95_ms = tracker_summary.get("p95_latency_ms", ops.get("p95_ms", 0))

    # Check for 429 errors
    error_429_count = 0
    for p in profiles:
        for ev in p.get("evidence", {}).values():
            if isinstance(ev, dict) and "429" in str(ev.get("note", "")):
                error_429_count += 1

    res = {
        "run_id": run_id,
        "companies": expected_count,
        "workers": workers,
        "wall_clock_seconds": elapsed_wall,
        "total_http_requests": total_requests,
        "requests_per_company": round(total_requests / expected_count, 2),
        "total_claims": total_claims,
        "claims_per_company": claims_per_co,
        "evidence_per_company": evidence_per_co,
        "website_available": website_statuses.get("available", 0),
        "website_ambiguous": website_statuses.get("ambiguous", 0),
        "website_blocked": website_statuses.get("blocked", 0),
        "website_not_available": website_statuses.get("not_available", 0),
        "rate_limit_429_errors": error_429_count,
        "p50_latency_ms": p50_ms,
        "p95_latency_ms": p95_ms,
    }

    print(f"DONE: {elapsed_wall}s, {total_requests} reqs ({res['requests_per_company']} req/co), "
          f"claims/co={claims_per_co}, 429s={error_429_count}, p50={p50_ms}ms, p95={p95_ms}ms")
    return res


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "10"
    cli_workers = [int(x) for x in sys.argv[2:] if x.isdigit()]
    base_dir = ROOT / "results" / "benchmarks"

    if target in ("10", "all"):
        workers_10 = cli_workers or [1, 4, 8]
        data_10 = ROOT / "results" / "test_reports" / "test_10_orgs.jsonl"
        out_10 = base_dir / "benchmark_10_results.json"
        existing_10 = {}
        if out_10.exists():
            try:
                for item in json.loads(out_10.read_text(encoding="utf-8")):
                    existing_10[item["workers"]] = item
            except Exception:
                pass

        for w in workers_10:
            res = run_single_benchmark(
                dataset_path=data_10,
                expected_count=10,
                workers=w,
                run_id=f"benchmark_10_w{w}",
                output_dir=base_dir / f"benchmark_10_w{w}",
            )
            existing_10[w] = res

        sorted_10 = [existing_10[w] for w in sorted(existing_10.keys())]
        out_10.write_text(json.dumps(sorted_10, indent=2), encoding="utf-8")
        print("\n=== 10-Company Results ===")
        print(json.dumps(sorted_10, indent=2))

    if target in ("50", "all"):
        workers_50 = cli_workers or [1, 4, 8, 12, 16]
        data_50 = ROOT / "results" / "website_discovery" / "test_50_orgs.jsonl"
        out_50 = base_dir / "benchmark_50_results.json"
        existing_50 = {}
        if out_50.exists():
            try:
                for item in json.loads(out_50.read_text(encoding="utf-8")):
                    existing_50[item["workers"]] = item
            except Exception:
                pass

        for w in workers_50:
            res = run_single_benchmark(
                dataset_path=data_50,
                expected_count=50,
                workers=w,
                run_id=f"benchmark_50_w{w}",
                output_dir=base_dir / f"benchmark_50_w{w}",
            )
            existing_50[w] = res

        sorted_50 = [existing_50[w] for w in sorted(existing_50.keys())]
        out_50.write_text(json.dumps(sorted_50, indent=2), encoding="utf-8")
        print("\n=== 50-Company Results ===")
        print(json.dumps(sorted_50, indent=2))


if __name__ == "__main__":
    main()
