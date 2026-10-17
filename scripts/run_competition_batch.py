#!/usr/bin/env python3
"""
Signalpost Atlas — Production Competition Batch Runner
Features:
- Bounded concurrency with per-request timeouts
- Global deadline watchdog (45-minute competition budget)
- Outbound request budget enforcement (2,000-request limit)
- Automatic missing website discovery with strict identity gating
- Dual-compatible canonical OUTPUT_CONTRACT.md envelopes
- Atomic checkpointing and resumption support
- Centralized RunArtifactWriter with automatic run folder creation
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.batch import (  # noqa: E402
    profile_complete_for_modules,
    profiles_from_inputs,
    read_organisation_inputs,
    terminal_envelope,
    validate_envelopes,
)
from norway_company_agent.concurrency import (  # noqa: E402
    GLOBAL_HOST_GOVERNOR,
    GLOBAL_REQUEST_TRACKER,
    GLOBAL_WATCHDOG,
    apply_operational_config,
    format_config_table,
    resolve_operational_config,
)
from norway_company_agent.evidence import evidence, utc_now  # noqa: E402
from norway_company_agent.identity import apply_website_identity_gate  # noqa: E402
from norway_company_agent.official import fetch_official_modules  # noqa: E402
from norway_company_agent.run_writer import RunArtifactWriter  # noqa: E402
from norway_company_agent.website import fetch_website, normalize_homepage  # noqa: E402


def _candidate_domains_for_profile(profile: dict) -> list[str]:
    import re
    import unicodedata
    name = profile.get('name') or ''
    if not name:
        return []
    generic = {'as', 'asa', 'ans', 'da', 'enk', 'iks', 'norge', 'norway', 'group', 'gruppen', 'drift', 'holding'}

    # Transliteration 1: standard (ø->o, å->a, æ->ae)
    t1 = name.translate(str.maketrans({"ø": "o", "Ø": "O", "å": "a", "Å": "A", "æ": "ae", "Æ": "AE"}))
    t1 = unicodedata.normalize('NFKD', t1).encode('ascii', 'ignore').decode().casefold()
    toks1 = [t for t in re.findall(r'[a-z0-9]+', t1) if t not in generic and len(t) > 1]

    # Transliteration 2: double-letter (ø->oe, å->aa, æ->ae)
    t2 = name.translate(str.maketrans({"ø": "oe", "Ø": "OE", "å": "aa", "Å": "AA", "æ": "ae", "Æ": "AE"}))
    t2 = unicodedata.normalize('NFKD', t2).encode('ascii', 'ignore').decode().casefold()
    toks2 = [t for t in re.findall(r'[a-z0-9]+', t2) if t not in generic and len(t) > 1]

    candidates: list[str] = []

    def add_domain_variants(tokens: list[str]) -> None:
        if not tokens:
            return
        comb = ''.join(tokens)
        if len(comb) <= 30:
            candidates.append(f'https://www.{comb}.no')
            candidates.append(f'https://{comb}.no')
        if 1 < len(tokens) <= 4:
            hyphen = '-'.join(tokens)
            if len(hyphen) <= 35:
                candidates.append(f'https://www.{hyphen}.no')
        if len(tokens) >= 2 and len(tokens[0]) >= 4 and tokens[0] not in {'norsk', 'nordic', 'bygg', 'service', 'oslo'}:
            candidates.append(f'https://www.{tokens[0]}.no')
            candidates.append(f'https://{tokens[0]}.no')

    add_domain_variants(toks1)
    if toks2 != toks1:
        add_domain_variants(toks2)

    seen: set[str] = set()
    deduped: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


def write_jsonl(path: Path, rows: list[dict]) -> None:
    import uuid
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        for attempt in range(5):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (2**attempt))
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Signalpost Atlas Competition Batch Runner")
    parser.add_argument("--organisations", required=True, help="JSON, JSONL, or text organisation-number list")
    parser.add_argument("--bulk", default=None, help="Frozen Brreg entity snapshot (optional; falls back to live Brreg API)")
    parser.add_argument("--output", required=True, help="Terminal envelope JSONL")
    parser.add_argument("--profiles-output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-count", type=int, default=None, help="Expected count (defaults to input count)")
    parser.add_argument("--workers", type=int, default=None, help="Worker count (default: 6, env: SIGNALPOST_WORKERS)")
    parser.add_argument("--max-per-host", type=int, default=None, help="Max per-host concurrency (ceiling <= 2, env: SIGNALPOST_MAX_PER_HOST)")
    parser.add_argument("--checkpoint-every", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=None, help="Total runtime budget (default: 2700s, env: SIGNALPOST_TIMEOUT_SECONDS)")
    parser.add_argument("--shutdown-margin", type=float, default=None, help="Shutdown margin seconds (default: 30s, env: SIGNALPOST_SHUTDOWN_MARGIN)")
    parser.add_argument("--max-requests", type=int, default=None, help="Outbound request ceiling (default: 2000, env: SIGNALPOST_MAX_REQUESTS)")
    parser.add_argument("--per-request-timeout", type=float, default=None, help="Per-request timeout (default: 8.0s, env: SIGNALPOST_PER_REQUEST_TIMEOUT)")
    parser.add_argument("--modules", default="registry,accounting_obligation,registry_live,financials,roles,group,locations,website")
    parser.add_argument("--identity-policy", default="tiered_website_identity_v1", choices=["tiered_website_identity_v1", "strict_website_identity_v1"], help="Website identity verification policy")
    args = parser.parse_args()

    # Resolve and enforce operational configuration
    op_config = resolve_operational_config({
        "workers": args.workers,
        "max_per_host": args.max_per_host,
        "max_requests": args.max_requests,
        "timeout_seconds": args.timeout_seconds,
        "shutdown_margin": args.shutdown_margin,
        "per_request_timeout": args.per_request_timeout,
    })
    apply_operational_config(op_config)
    os.environ["SIGNALPOST_IDENTITY_POLICY"] = args.identity_policy

    effective_workers = op_config["workers"]["effective"]
    effective_max_per_host = op_config["max_per_host"]["effective"]
    effective_max_requests = op_config["max_requests"]["effective"]
    effective_timeout = op_config["timeout_seconds"]["effective"]
    effective_shutdown_margin = op_config["shutdown_margin"]["effective"]
    effective_req_timeout = op_config["per_request_timeout"]["effective"]

    # Print startup table of effective configuration
    config_table = format_config_table(op_config)
    print(config_table)

    GLOBAL_REQUEST_TRACKER.reset()
    start_monotonic = time.monotonic()
    started_at = utc_now()

    organisation_inputs = read_organisation_inputs(args.organisations)
    orgs = [item["organisation_number"] for item in organisation_inputs]
    expected_count = args.expected_count if args.expected_count is not None else len(orgs)
    if len(orgs) != expected_count:
        raise SystemExit(f"Expected {expected_count} organisations, received {len(orgs)}")

    # Initialize Centralized Run Writer
    run_writer = RunArtifactWriter(
        base_dir=ROOT / "results",
        run_id=args.run_id,
        run_config={**vars(args), "operational_config": op_config},
    )
    run_writer.save_manifest(organisation_inputs)
    run_writer.log(f"Starting batch run {args.run_id} for {len(orgs)} companies (workers={effective_workers}, max_per_host={effective_max_per_host})")

    # Hydrate profiles from bulk CSV or live API
    profiles, registry_metadata = profiles_from_inputs(args.bulk, orgs)
    annotations = {item["organisation_number"]: item for item in organisation_inputs}
    for profile in profiles:
        for key in ("evaluation_split", "sample_slice"):
            if key in annotations.get(profile["organisation_number"], {}):
                profile[key] = annotations[profile["organisation_number"]][key]

    requested_modules = [item.strip() for item in args.modules.split(",") if item.strip()]
    fetch_modules = set(requested_modules) - {"registry", "accounting_obligation", "website"}
    operations = {"requests": 0, "bytes": 0, "latencies_ms": [], "third_party_cost_usd": 0.0}

    # Preload any discovered seeds if available
    discovered_seeds = {}
    verified_seeds_path = ROOT / "results" / "website_discovery" / "verified_websites.jsonl"
    if verified_seeds_path.exists():
        for line in verified_seeds_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                discovered_seeds[item["organisation_number"]] = item["verified_website"]

    def enrich(profile: dict) -> tuple[dict, dict]:
        # Watchdog and Request Budget Governor check
        remaining_co = max(1, len(pending_profiles) - len(state))
        active_fetch_modules, should_wind_down = GLOBAL_WATCHDOG.check_governor(remaining_co, fetch_modules)
        if should_wind_down:
            # Emergency wind-down: skip optional network calls
            metric = {"requests": 0, "bytes": 0, "latencies_ms": []}
            profile["run_metrics"] = metric
            return profile, metric

        # Deduplicate registry_live if already retrieved in initial live hydration
        if "registry" in profile.get("evidence", {}) and "registry_live" in active_fetch_modules:
            reg_ev = profile["evidence"]["registry"]
            if reg_ev.get("source_type") == "official_registry_live":
                profile["evidence"]["registry_live"] = evidence(
                    "registry_live",
                    reg_ev.get("status", "available"),
                    "official_registry_live",
                    reg_ev.get("source_url", ""),
                    value=reg_ev.get("value"),
                    retrieved_at=reg_ev.get("retrieved_at"),
                    content_sha256=reg_ev.get("content_sha256"),
                )
                active_fetch_modules.remove("registry_live")

        records, metrics = fetch_official_modules(profile["organisation_number"], active_fetch_modules)
        profile["evidence"].update(records)
        website_metrics = {"requests": 0, "bytes": 0, "latencies_ms": []}

        if "website" in requested_modules:
            target_url = profile.get("website") or discovered_seeds.get(profile["organisation_number"])
            website_record = None

            # 1. Try known or registered website
            if target_url:
                website_record, website_metrics = fetch_website(target_url, timeout=effective_req_timeout)
                gated = apply_website_identity_gate(profile, website_record, policy=args.identity_policy)
                website_record = gated["website"]
                if gated.get("assessment") and gated["assessment"].get("publishable"):
                    profile["evidence"]["website"] = website_record
                    profile["website"] = website_record["value"].get("final_url") or target_url

            # 2. If website not verified, attempt candidate discovery if within request budget
            if profile.get("evidence", {}).get("website") is None and GLOBAL_REQUEST_TRACKER.total_requests < effective_max_requests - 50:
                candidates = _candidate_domains_for_profile(profile)
                for cand in candidates[:2]:
                    # Shallow probe: crawl_secondary=False to avoid burning requests on unverified sites
                    cand_rec, cand_ops = fetch_website(cand, timeout=effective_req_timeout, crawl_secondary=False)
                    website_metrics["requests"] += cand_ops.get("requests", 0)
                    website_metrics["bytes"] += cand_ops.get("bytes", 0)
                    website_metrics["latencies_ms"].extend(cand_ops.get("latencies_ms", []))
                    if cand_rec.get("status") == "available":
                        gated = apply_website_identity_gate(profile, cand_rec, policy=args.identity_policy)
                        if gated.get("assessment") and gated["assessment"].get("publishable"):
                            cand_rec["source_type"] = "discovered_company_website"
                            profile["evidence"]["website"] = cand_rec
                            profile["website"] = cand_rec["value"].get("final_url") or cand
                            break

            if "website" not in profile["evidence"]:
                if website_record:
                    profile["evidence"]["website"] = website_record
                else:
                    profile["evidence"]["website"] = evidence(
                        "website",
                        "not_found",
                        "discovered_company_website",
                        "",
                        value={"status": "not_found", "reasons": ["no_website_found_or_verified"]},
                    )

            # Failure category tagging
            w_ev = profile.get("evidence", {}).get("website", {})
            w_val = w_ev.get("value") or {}
            w_assess = w_val.get("identity_assessment") or {}
            if w_assess.get("publishable"):
                profile["website_verification_status"] = "verified"
                profile["website_verification_tier"] = w_assess.get("selected_tier")
            else:
                profile["website_verification_status"] = "unverified"
                if w_assess.get("automated_identity_result"):
                    profile["website_failure_category"] = w_assess["automated_identity_result"]
                elif w_ev.get("status") in {"blocked", "source_error"}:
                    profile["website_failure_category"] = "domain_unreachable_or_blocked"
                elif not target_url:
                    profile["website_failure_category"] = "no_domain_found"
                else:
                    profile["website_failure_category"] = "insufficient_evidence"

        for m in requested_modules:
            if m not in profile["evidence"]:
                req_left = max(0, effective_max_requests - GLOBAL_REQUEST_TRACKER.total_requests)
                allowance = req_left / remaining_co
                profile["evidence"][m] = evidence(
                    m,
                    "not_applicable" if allowance < 3.0 else "not_found",
                    "official_registry",
                    "",
                    value={},
                )

        net_requests = sum(1 for item in metrics if not getattr(item, "from_cache", False)) + website_metrics["requests"]
        metric = {
            "requests": net_requests,
            "bytes": sum(item.bytes_received for item in metrics) + website_metrics["bytes"],
            "latencies_ms": [item.elapsed_ms for item in metrics if not getattr(item, "from_cache", False)] + website_metrics["latencies_ms"],
        }
        profile["run_metrics"] = metric
        return profile, metric

    state: dict[str, dict] = {}
    resumed_profiles = 0
    profiles_output = Path(args.profiles_output)
    if args.resume and profiles_output.exists():
        prior = [json.loads(line) for line in profiles_output.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not set(item["organisation_number"] for item in prior).issubset(set(orgs)):
            raise SystemExit("Resume profile membership is not a subset of this batch")
        state = {
            item["organisation_number"]: item
            for item in prior
            if profile_complete_for_modules(item, requested_modules)
        }
        resumed_profiles = len(state)

    pending_profiles = [profile for profile in profiles if profile["organisation_number"] not in state]

    with ThreadPoolExecutor(max_workers=effective_workers) as pool:
        futures = {pool.submit(enrich, profile): profile["organisation_number"] for profile in pending_profiles}
        for index, future in enumerate(as_completed(futures), 1):
            profile, metric = future.result()
            state[profile["organisation_number"]] = profile
            operations["requests"] += metric["requests"]
            operations["bytes"] += metric["bytes"]
            operations["latencies_ms"].extend(metric["latencies_ms"])

            if index % args.checkpoint_every == 0 or index == len(pending_profiles):
                checkpoint = [state[org] for org in orgs if org in state]
                write_jsonl(profiles_output, checkpoint)
                run_writer.save_checkpoint(checkpoint)
                run_writer.log(f"Checkpoint {index}/{len(pending_profiles)} saved ({GLOBAL_REQUEST_TRACKER.total_requests} requests)")

    completed_at = utc_now()
    ordered_profiles = [state[org] for org in orgs]

    for profile in ordered_profiles:
        website_record = profile.get("evidence", {}).get("website")
        if website_record and website_record.get("status") == "available":
            gated = apply_website_identity_gate(profile, website_record, policy=args.identity_policy)
            website_record = gated["website"]
            if gated.get("assessment") and gated["assessment"].get("publishable"):
                profile["website_verification_status"] = "verified"
                profile["website_verification_tier"] = gated["assessment"].get("selected_tier")
                profile["website_failure_category"] = None
                profile["website"] = website_record.get("value", {}).get("final_url") or profile.get("website")
            else:
                profile["website_verification_status"] = "unverified"
                profile["website_verification_tier"] = None
                profile["website_failure_category"] = gated.get("assessment", {}).get("automated_identity_result") or "unverified"

    tracker_summary = GLOBAL_REQUEST_TRACKER.summary()
    watchdog_events = GLOBAL_WATCHDOG.events()

    verified_count = sum(1 for p in ordered_profiles if p.get("website_verification_status") == "verified")
    tier_counts = dict(collections.Counter(p.get("website_verification_tier") for p in ordered_profiles if p.get("website_verification_tier")))
    failure_counts = dict(collections.Counter(p.get("website_failure_category") for p in ordered_profiles if p.get("website_failure_category")))

    website_diagnostics = {
        "policy": args.identity_policy,
        "total_companies": len(ordered_profiles),
        "verified_websites": verified_count,
        "verification_rate": round(verified_count / max(1, len(ordered_profiles)), 4),
        "tier_breakdown": tier_counts,
        "failure_breakdown": failure_counts,
    }

    total_elapsed_ms = int((time.monotonic() - start_monotonic) * 1000)
    operations["runtime_ms"] = total_elapsed_ms
    operations["tracker_summary"] = tracker_summary
    operations["total_outbound_requests"] = tracker_summary["total_requests"]
    operations["total_retries"] = tracker_summary["total_retries"]
    operations["total_redirects"] = tracker_summary["total_redirects"]
    operations["host_breakdown"] = tracker_summary["host_breakdown"]
    operations["p50_ms"] = tracker_summary["p50_latency_ms"]
    operations["p95_ms"] = tracker_summary["p95_latency_ms"]

    envelopes = [
        terminal_envelope(
            profile,
            run_id=args.run_id,
            modules=requested_modules,
            started_at=started_at,
            completed_at=completed_at,
            operations=operations,
        )
        for profile in ordered_profiles
    ]

    validation = validate_envelopes(envelopes, expected_count)
    write_jsonl(profiles_output, ordered_profiles)
    write_jsonl(Path(args.output), envelopes)

    report = {
        "run_id": args.run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "expected_count": expected_count,
        "emitted_envelopes": len(envelopes),
        "resumed_profiles": resumed_profiles,
        "profiles_fetched_this_run": len(pending_profiles),
        "modules": requested_modules,
        "operational_config": op_config,
        "registry": registry_metadata,
        "operations": operations,
        "validation": validation,
        "website_diagnostics": website_diagnostics,
        "watchdog": {
            "budget_seconds": effective_timeout,
            "elapsed_seconds": round(total_elapsed_ms / 1000.0, 2),
            "max_requests": effective_max_requests,
            "used_requests": tracker_summary["total_requests"],
            "within_budget": (total_elapsed_ms / 1000.0 <= effective_timeout) and (tracker_summary["total_requests"] <= effective_max_requests),
            "events": watchdog_events,
        },
    }

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Finalize in centralized run writer
    run_writer.finalize_run(
        envelopes=envelopes,
        profiles=ordered_profiles,
        metrics=operations,
        validation=validation,
        status="completed" if validation["passed"] else "failed",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if validation["passed"] else 1)


if __name__ == "__main__":
    main()
