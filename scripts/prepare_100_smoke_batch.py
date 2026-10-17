#!/usr/bin/env python3
"""
Select exactly 100 permitted test companies for the official Builderr smoke test.
Combines the 50 companies from the existing benchmark with 50 diverse new active
companies from Brønnøysundregistrene (NLOD 2.0 open data license).
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXISTING_PATH = ROOT / "results" / "website_discovery" / "test_50_orgs.jsonl"
OUTPUT_PATH = ROOT / "results" / "test_reports" / "smoke_100_orgs.jsonl"


def fetch_url(url: str, retries: int = 3) -> dict:
    headers = {"User-Agent": "signalpost-atlas-smoke/1.0 (NLOD 2.0 research)"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            if attempt == retries - 1:
                raise
            time.sleep(1.0 * (attempt + 1))
    return {}


def main() -> None:
    orgs = []
    seen = set()

    # 1. Load existing 50 benchmark organisations
    if EXISTING_PATH.exists():
        for line in EXISTING_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                num = item.get("organisation_number")
                if num and num not in seen:
                    seen.add(num)
                    orgs.append(num)

    print(f"Loaded {len(orgs)} existing benchmark organisations")

    # 2. Query official Brreg API for 50 additional active companies in smaller chunks
    page = 0
    while len(orgs) < 100 and page < 10:
        url = f"https://data.brreg.no/enhetsregisteret/api/enheter?organisasjonsform=ASA&page={page}&size=20"
        data = fetch_url(url)
        for entry in data.get("_embedded", {}).get("enheter", []):
            num = entry.get("organisasjonsnummer")
            if num and num not in seen and len(orgs) < 100:
                seen.add(num)
                orgs.append(num)
        page += 1

    page = 1
    while len(orgs) < 100 and page < 20:
        url = f"https://data.brreg.no/enhetsregisteret/api/enheter?organisasjonsform=AS&page={page}&size=20"
        data = fetch_url(url)
        for entry in data.get("_embedded", {}).get("enheter", []):
            num = entry.get("organisasjonsnummer")
            if num and num not in seen and len(orgs) < 100:
                seen.add(num)
                orgs.append(num)
        page += 1

    if len(orgs) != 100:
        raise SystemExit(f"Failed to gather exactly 100 companies, got {len(orgs)}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for org in orgs:
            f.write(json.dumps({"organisation_number": org}) + "\n")

    print(f"Successfully wrote exactly {len(orgs)} companies to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
