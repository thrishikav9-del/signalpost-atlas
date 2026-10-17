#!/usr/bin/env python3
"""
Step 3: Audit of Strict-Identity Evidence and Output Verification
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 1. Preserve the run
backup_dir = ROOT / "results" / "runs" / "smoke_100_strict_identity_preserved"
backup_dir.mkdir(parents=True, exist_ok=True)

submission_dir = ROOT / "results" / "submission"
for fname in ["smoke_envelopes.jsonl", "smoke_profiles.jsonl", "smoke_report.json"]:
    src = submission_dir / fname
    dst = backup_dir / fname
    if src.exists():
        shutil.copy2(src, dst)
        print(f"Preserved {fname} -> {dst}")

# 2. Load envelopes and profiles
envelopes_path = submission_dir / "smoke_envelopes.jsonl"
profiles_path = submission_dir / "smoke_profiles.jsonl"
report_path = submission_dir / "smoke_report.json"

with open(envelopes_path, "r", encoding="utf-8") as f:
    envelopes = [json.loads(line) for line in f if line.strip()]

with open(profiles_path, "r", encoding="utf-8") as f:
    profiles = [json.loads(line) for line in f if line.strip()]

with open(report_path, "r", encoding="utf-8") as f:
    report = json.load(f)

profiles_by_org = {p["organisation_number"]: p for p in profiles}

# 3. Audit all available websites
print("\n=== AUDITING AVAILABLE WEBSITES ===")
available_audits = []

for env in envelopes:
    web_claim = next((c for c in env.get("claims", []) if c.get("field") == "official_website" and c.get("availability") == "available"), None)
    if not web_claim:
        continue
    org = env["organisation_number"]
    prof = profiles_by_org.get(org, {})
    legal_name = next((c.get("value") for c in env.get("claims", []) if c.get("field") == "legal_name"), prof.get("name"))
    
    site_ev = prof.get("evidence", {}).get("website", {})
    site_val = site_ev.get("value", {}) if isinstance(site_ev.get("value"), dict) else {}
    assessment = site_val.get("identity_assessment", {})
    
    ev_id = web_claim.get("evidence_ids", [None])[0]
    ev_rec = next((e for e in env.get("evidence", []) if e.get("id") == ev_id), {})
    
    b_addr = prof.get("business_address") or {}
    p_addr = prof.get("postal_address") or {}
    
    audit_entry = {
        "org": org,
        "legal_name": legal_name,
        "claim_value": web_claim.get("value"),
        "final_url": site_val.get("final_url"),
        "source_url": site_ev.get("source_url"),
        "condition_passed": assessment.get("condition_passed"),
        "automated_identity_result": assessment.get("automated_identity_result"),
        "score": assessment.get("score"),
        "legal_name_tokens": assessment.get("legal_name_tokens"),
        "matched_tokens": assessment.get("matched_tokens"),
        "page_title": site_val.get("title"),
        "page_h1": site_val.get("h1"),
        "registered_postcode": prof.get("postcode") or b_addr.get("postnummer"),
        "registered_address": prof.get("address") or b_addr.get("adresse"),
        "registered_poststed": prof.get("poststed") or b_addr.get("poststed"),
        "registered_municipality": prof.get("municipality") or b_addr.get("kommune"),
        "identity_evidence": assessment.get("identity_evidence"),
        "claim_span": ev_rec.get("claim_span"),
        "retrieved_at": ev_rec.get("retrieved_at"),
        "source_url_evidence": ev_rec.get("source_url"),
        "reasons": assessment.get("reasons"),
    }
    available_audits.append(audit_entry)
    print(f"Found available: {org} - {legal_name} -> {web_claim.get('value')}")

# Save detailed available audits
with open(backup_dir / "available_audits.json", "w", encoding="utf-8") as f:
    json.dump(available_audits, f, indent=2, ensure_ascii=False)

# 4. Audit all 6 conflicting identifier cases
print("\n=== AUDITING CONFLICTING IDENTIFIER CASES ===")
conflict_audits = []

for prof in profiles:
    site_ev = prof.get("evidence", {}).get("website", {})
    site_val = site_ev.get("value", {}) if isinstance(site_ev.get("value"), dict) else {}
    assessment = site_val.get("identity_assessment", {})
    
    if assessment.get("automated_identity_result") == "conflicting_identifier":
        org = prof.get("organisation_number")
        name = prof.get("name")
        c_url = site_val.get("final_url") or site_ev.get("source_url") or prof.get("website")
        ev_data = assessment.get("identity_evidence", {})
        reasons = assessment.get("reasons", [])
        
        conflict_audits.append({
            "org": org,
            "name": name,
            "url": c_url,
            "reasons": reasons,
            "excerpt": ev_data.get("excerpt"),
            "location": ev_data.get("location"),
            "title": site_val.get("title"),
            "main_text_excerpt": site_val.get("main_text_excerpt", "")[:300],
        })
        print(f"Conflict: {org} ({name}) -> {reasons}")

with open(backup_dir / "conflict_audits.json", "w", encoding="utf-8") as f:
    json.dump(conflict_audits, f, indent=2, ensure_ascii=False)

# 5. Output consistency checks
print("\n=== OUTPUT CONSISTENCY CHECKS ===")
errors = []

# Exactly one output per input org
input_orgs_path = ROOT / "results" / "test_reports" / "smoke_100_orgs.jsonl"
with open(input_orgs_path, "r", encoding="utf-8") as f:
    expected_orgs = [json.loads(line)["organisation_number"] for line in f if line.strip()]

emitted_orgs = [env["organisation_number"] for env in envelopes]

if len(expected_orgs) != len(emitted_orgs):
    errors.append(f"Expected {len(expected_orgs)} envelopes, got {len(emitted_orgs)}")

if set(expected_orgs) != set(emitted_orgs):
    errors.append("Mismatch in organisation numbers between input and output")

# Check alignment
for i, (exp, em) in enumerate(zip(expected_orgs, emitted_orgs)):
    if exp != em:
        errors.append(f"Order alignment mismatch at index {i}: expected {exp}, got {em}")

allowed_states = {"available", "not_available", "blocked", "not_applicable", "ambiguous", "failed"}

for idx, env in enumerate(envelopes):
    org = env["organisation_number"]
    prof = profiles_by_org.get(org, {})
    site_ev = prof.get("evidence", {}).get("website", {})
    site_val = site_ev.get("value", {}) if isinstance(site_ev.get("value"), dict) else {}
    assessment = site_val.get("identity_assessment", {})
    
    # Check claim availability vs assessment
    web_claim = next((c for c in env.get("claims", []) if c.get("field") == "official_website"), None)
    if web_claim:
        av = web_claim.get("availability")
        if av not in allowed_states:
            errors.append(f"{org}: invalid availability state {av}")
        
        # Verify consistency with assessment
        if av == "available":
            if not assessment.get("publishable"):
                errors.append(f"{org}: claimed available but identity assessment publishable is False")
        elif av == "ambiguous":
            if assessment.get("publishable"):
                errors.append(f"{org}: claimed ambiguous but identity assessment publishable is True")
        elif av == "blocked":
            if site_ev.get("status") != "blocked":
                errors.append(f"{org}: claimed blocked but site evidence status is {site_ev.get('status')}")
    
    # Check evidence validity
    ev_ids = {e.get("id") for e in env.get("evidence", [])}
    for c in env.get("claims", []):
        for eid in c.get("evidence_ids", []):
            if eid not in ev_ids:
                errors.append(f"{org}: claim {c.get('field')} references unknown evidence {eid}")
    
    for e in env.get("evidence", []):
        for field in ["id", "source_url", "source_class", "retrieved_at", "content_sha256", "claim_span"]:
            if field not in e or e[field] is None:
                errors.append(f"{org}: evidence {e.get('id')} missing {field}")
                
    # Human review check
    if assessment and assessment.get("human_review_status") != "not_reviewed":
        errors.append(f"{org}: human_review_status is {assessment.get('human_review_status')} (must be not_reviewed)")

print(f"Total consistency check errors: {len(errors)}")
if errors:
    for e in errors[:10]:
        print("  ERROR:", e)
else:
    print("ALL 100 ENVELOPES PASS 100% CONSISTENCY AND OUTPUT CONTRACT CHECKS!")
