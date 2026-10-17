import json

with open("results/benchmarks/benchmark_50_tiered/profiles.jsonl", encoding="utf-8") as f:
    idx = 0
    for line in f:
        p = json.loads(line)
        w_ev = p.get("evidence", {}).get("website") or {}
        w_val = w_ev.get("value") or {}
        assess = w_val.get("identity_assessment") or {}
        if assess.get("publishable"):
            idx += 1
            print(f"{idx}. {p.get('name')} ({p.get('organisation_number')}) -> {w_val.get('final_url')}")
            print(f"   Tier: {assess.get('selected_tier')} | Score: {assess.get('score')} | Cond: {assess.get('condition_passed')}")
            print(f"   Tokens: {assess.get('matched_tokens')} | Muni: {p.get('municipality')} | Postcode: {p.get('postcode')}")
            ev = assess.get("identity_evidence") or {}
            print(f"   Location: {ev.get('extracted_matching_evidence', {}).get('location')}")
            print(f"   Excerpt: {ev.get('excerpt')[:120] if ev.get('excerpt') else None}")
            print()
