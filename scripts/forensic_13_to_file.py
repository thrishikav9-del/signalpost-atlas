import json

with open("results/benchmarks/benchmark_50_tiered/profiles.jsonl", encoding="utf-8") as f, open("scripts/forensic_13_raw.txt", "w", encoding="utf-8") as out:
    idx = 0
    for line in f:
        p = json.loads(line)
        w_ev = p.get("evidence", {}).get("website") or {}
        w_val = w_ev.get("value") or {}
        assess = w_val.get("identity_assessment") or {}
        if assess.get("publishable"):
            idx += 1
            name = p.get("name")
            org = p.get("organisation_number")
            muni = p.get("municipality")
            postcode = p.get("postcode")
            addr = p.get("address")
            reg_web = p.get("website")
            tier = assess.get("selected_tier")
            cond = assess.get("condition_passed")
            url = w_val.get("final_url")
            domain = w_val.get("registered_domain")
            title = w_val.get("title")
            h1 = w_val.get("h1")
            tokens = assess.get("matched_tokens")
            ext = assess.get("identity_evidence", {}).get("extracted_matching_evidence", {})
            excerpt = assess.get("identity_evidence", {}).get("excerpt")

            out.write(f"=== [{idx}] {name} ({org}) ===\n")
            out.write(f"Registry: Muni: {muni} | Postcode: {postcode} | Addr: {addr} | RegWeb: {reg_web}\n")
            out.write(f"Website URL: {url} | Domain: {domain}\n")
            out.write(f"Tier: {tier} | Cond: {cond} | Score: {assess.get('score')}\n")
            out.write(f"Title: {title}\n")
            out.write(f"H1: {h1}\n")
            out.write(f"Matched Tokens: {tokens}\n")
            out.write(f"Extracted: {json.dumps(ext, ensure_ascii=False)}\n")
            out.write(f"Excerpt: {excerpt}\n\n")
