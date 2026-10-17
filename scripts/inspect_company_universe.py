"""
Inspect Official Builderr Signalpost Company Universe
Streams download from official URL, computes SHA-256, analyzes schema and fields.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FILE = DATA_DIR / "signalpost-company-universe-2025.jsonl.gz"
SOURCE_URL = "https://builderr.ai/signalpost-company-universe-2025.jsonl.gz"


def download_and_inspect():
    print(f"Streaming from {SOURCE_URL}...")
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "builderr-signalpost-poc/0.1 (+https://builderr.ai)"})

    hasher = hashlib.sha256()
    bytes_downloaded = 0

    with urllib.request.urlopen(req, timeout=30) as resp:
        with TARGET_FILE.open("wb") as f_out:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                hasher.update(chunk)
                f_out.write(chunk)
                bytes_downloaded += len(chunk)

    sha256_hex = hasher.hexdigest()
    print(f"Downloaded {bytes_downloaded} bytes. SHA256: {sha256_hex}")

    # Inspect schema
    total_records = 0
    sample_records = []
    all_keys = set()
    field_frequencies = {}

    print("Analyzing records inside gzipped JSONL...")
    with gzip.open(TARGET_FILE, "rt", encoding="utf-8") as gz:
        for i, line in enumerate(gz):
            line = line.strip()
            if not line:
                continue
            total_records += 1
            row = json.loads(line)
            all_keys.update(row.keys())
            for k in row.keys():
                field_frequencies[k] = field_frequencies.get(k, 0) + 1
            if len(sample_records) < 5:
                sample_records.append(row)

    report = {
        "source_url": SOURCE_URL,
        "bytes_compressed": bytes_downloaded,
        "sha256": sha256_hex,
        "total_records": total_records,
        "all_fields": sorted(list(all_keys)),
        "field_frequencies": field_frequencies,
        "sample_records": sample_records,
    }

    report_path = ROOT / "results" / "reports" / "official_universe_inspection.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== Universe Inspection Summary ===")
    print(f"Total entities: {total_records}")
    print(f"Fields available: {sorted(list(all_keys))}")
    print("\nSample Record 0:")
    print(json.dumps(sample_records[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    download_and_inspect()
