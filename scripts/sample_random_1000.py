"""
Signalpost Atlas — Reproducible 1,000-Company Random Sampler (Phase E)
Extracts a reproducible sample of 1,000 active companies using seed 42 from an official frozen snapshot.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.sampling import iter_bulk, normalize_row


def sample_1000_from_snapshot(
    snapshot_path: Path,
    output_path: Path,
    seed: int = 42,
    count: int = 1000,
) -> dict:
    if not snapshot_path.exists():
        raise FileNotFoundError(
            f"Snapshot file not found: {snapshot_path}\n"
            "An official frozen registry snapshot (e.g. enheter_alle.csv.gz from Brønnøysundregistrene open data) "
            "is required to generate the offline random sample without flooding the live API."
        )

    rng = random.Random(seed)
    candidates: list[dict] = []

    # Stream through snapshot with reservoir sampling
    total_seen = 0
    legal_forms = {}

    print(f"Streaming from snapshot {snapshot_path} (seed={seed}, target={count})...")
    for record in iter_bulk(snapshot_path):
        org = record.get("organisation_number")
        if not org or len(org) != 9 or not org.isdigit():
            continue
        # Filter for active companies (not bankrupt or liquidating)
        if record.get("bankrupt") or record.get("liquidating"):
            continue

        total_seen += 1
        form = record.get("legal_form") or "OTHER"
        legal_forms[form] = legal_forms.get(form, 0) + 1

        if len(candidates) < count:
            candidates.append(record)
        else:
            j = rng.randrange(total_seen)
            if j < count:
                candidates[j] = record

    if len(candidates) < count:
        raise ValueError(f"Snapshot contained only {len(candidates)} valid active entities; needed {count}")

    # Stable deterministic sort by hash
    candidates = sorted(candidates, key=lambda c: hashlib.sha256(f"{seed}:{c['organisation_number']}".encode()).hexdigest())

    # Format output items
    output_rows = []
    form_distribution = {}
    for c in candidates:
        form = c.get("legal_form") or "OTHER"
        form_distribution[form] = form_distribution.get(form, 0) + 1
        output_rows.append({
            "organisation_number": c["organisation_number"],
            "name": c.get("name", ""),
            "legal_form": form,
            "postcode": c.get("postcode", ""),
            "website": c.get("website", ""),
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for item in output_rows:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    metadata = {
        "seed": seed,
        "sample_size": len(output_rows),
        "total_active_scanned": total_seen,
        "unique_orgs": len(set(r["organisation_number"] for r in output_rows)),
        "legal_forms_represented": form_distribution,
        "output_file": str(output_path),
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }
    print(f"Sample generated successfully: {metadata['unique_orgs']} entities saved to {output_path}")
    print(f"Legal forms distribution: {form_distribution}")
    return metadata


def main():
    parser = argparse.ArgumentParser(description="Sample 1000 random companies from official registry snapshot")
    parser.add_argument("--snapshot", default="data/enheter_alle.csv.gz", help="Path to frozen enheter_alle.csv.gz snapshot")
    parser.add_argument("--output", default="data/random_1000_orgs.jsonl", help="Output JSONL path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--count", type=int, default=1000, help="Number of companies to sample")
    args = parser.parse_args()

    snapshot_file = Path(args.snapshot)
    if not snapshot_file.is_absolute():
        snapshot_file = ROOT / snapshot_file
    output_file = Path(args.output)
    if not output_file.is_absolute():
        output_file = ROOT / output_file

    try:
        sample_1000_from_snapshot(snapshot_file, output_file, seed=args.seed, count=args.count)
    except FileNotFoundError as exc:
        print(f"HALT: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
