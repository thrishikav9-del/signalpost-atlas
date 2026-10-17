#!/usr/bin/env python3
"""
Select exactly 50 companies from the verified test fixtures for Level B evaluation.
"""
import json
import re
from pathlib import Path

FIXTURES_DIR = Path("tests/fixtures")
OUTPUT_PATH = Path("results/website_discovery/test_50_orgs.jsonl")

def main():
    orgs = []
    seen = set()
    for fixture in sorted(FIXTURES_DIR.glob("*")):
        if fixture.is_file():
            text = fixture.read_text(encoding="utf-8")
            matches = re.findall(r"\b[89]\d{8}\b", text)
            for m in matches:
                if m not in seen and m != "999999999":  # exclude synthetic dummy
                    seen.add(m)
                    orgs.append(m)
                    if len(orgs) == 50:
                        break
        if len(orgs) == 50:
            break

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for org in orgs:
            f.write(json.dumps({"organisation_number": org}) + "\n")

    print(f"Wrote {len(orgs)} companies to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
