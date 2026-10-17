import json

with open("results/benchmarks/benchmark_50_tiered/profiles.jsonl", encoding="utf-8") as f:
    for line in f:
        p = json.loads(line)
        w_ev = p.get("evidence", {}).get("website") or {}
        w_val = w_ev.get("value") or {}
        assess = w_val.get("identity_assessment") or {}
        if assess.get("publishable"):
            print("=" * 80)
            name = p.get("name")
            org = p.get("organisation_number")
            form = p.get("legal_form")
            muni = p.get("municipality")
            postcode = p.get("postcode")
            addr = p.get("address")
            reg_web = p.get("website")
            tier = assess.get("selected_tier")
            result = assess.get("automated_identity_result")
            score = assess.get("score")
            cond = assess.get("condition_passed")
            final_url = w_val.get("final_url")
            reg_domain = w_val.get("registered_domain")
            title = w_val.get("title")
            h1 = w_val.get("h1")
            tokens = assess.get("matched_tokens")
            ev = assess.get("identity_evidence") or {}
            ext_ev = ev.get("extracted_matching_evidence") or {}
            excerpt = ev.get("excerpt")

            print(f"ORG: {name} ({org}) | Legal Form: {form}")
            print(f"REGISTRY DATA: Muni: {muni} | Postcode: {postcode} | Address: {addr} | RegWeb: {reg_web}")
            print(f"GATE RESULT: Tier: {tier} | Status: {result} | Score: {score} | Condition: {cond}")
            print(f"WEBSITE: URL: {final_url} | Domain: {reg_domain}")
            print(f"TITLE: {title}")
            print(f"H1: {h1}")
            print(f"MATCHED TOKENS: {tokens}")
            print(f"MATCHED EVIDENCE: {json.dumps(ext_ev, ensure_ascii=False)}")
            print(f"EVIDENCE EXCERPT: {excerpt}")
            pages = w_val.get("pages", [])
            print(f"SECONDARY PAGES CRAWLED ({len(pages)}):")
            for idx, pg in enumerate(pages[:3]):
                print(f"   [{idx+1}] {pg.get('url')} | Title: {pg.get('title')}")
