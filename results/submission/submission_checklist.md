# Signalpost Atlas — Final Hackathon Submission Package & Checklist

**Competition:** Signalpost: Build an Agent That Finds Company Information  
**Organizer:** Builderr.ai  
**Submission Gate:** Unstop & `submit@builderr.ai`  
**Evaluation Status:** **READY TO SUBMIT** (Pending Operator GitHub URL & Contact Details)  
**Verification Suite:** **152 passed, 5 subtests passed in 4.35s** (100% Hermetic Pass)  
**Smoke Test Status:** **100/100 Envelopes Emitted, 0 Dropped, 100% Schema Valid**  

---

## 1. Submission Metadata & Status Matrix

| Checklist Item | Field Status | Exact Value or Action Required |
| :--- | :---: | :--- |
| **Agent Name** | **CONFIRMED** | `Signalpost Atlas` |
| **Repository URL** | <span style="color:red">**MISSING**</span> | **Operator Action Required:** Provide public/private GitHub repository URL. (Do not invent). |
| **Exact Commit Hash** | <span style="color:red">**MISSING**</span> | **Operator Action Required:** Git repository is not yet initialized in this directory. Execute `git init`, `git add .`, and `git commit -m "Signalpost Atlas final submission"` to generate the exact SHA-1 commit hash before submission. |
| **Single Run Command** | **CONFIRMED** | See Section 2 below (`python scripts/run_competition_batch.py ...`) |
| **Smoke-Test Report** | **CONFIRMED** | [`results/submission/smoke_report.json`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/results/submission/smoke_report.json) |
| **Terminal Envelopes** | **CONFIRMED** | [`results/submission/smoke_envelopes.jsonl`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/results/submission/smoke_envelopes.jsonl) (100 canonical envelopes) |
| **Researched Profiles** | **CONFIRMED** | [`results/submission/smoke_profiles.jsonl`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/results/submission/smoke_profiles.jsonl) (100 profiles with evidence graph) |
| **Expected Cost** | **CONFIRMED** | **$0.00 USD** (Declared API cost: $0.00; zero paid search/LLM APIs required) |
| **Models & APIs Used** | **CONFIRMED** | Brønnøysundregistrene REST APIs (NLOD 2.0); Direct HTTP crawler with robots.txt & domain-level lock; Trafilatura content extractor. Zero paid models. |
| **Software Licences** | **CONFIRMED** | MIT License for Signalpost Atlas codebase; NLOD 2.0 for Norwegian Open Government Data. |
| **Contact Information** | <span style="color:red">**MISSING**</span> | **Operator Action Required:** Fill in participant name, student/institution email, and contact handle on the Unstop portal submission form. |

---

## 2. Authoritative Single Run Commands

### Standard Batch Execution (Live Registry API + Website Discovery)
To evaluate the agent on any input list of Norwegian organisation numbers (JSON, JSONL, or TXT):
```bash
python scripts/run_competition_batch.py \
  --organisations <path_to_organisations_file> \
  --output out/envelopes.jsonl \
  --profiles-output out/profiles.jsonl \
  --report out/report.json \
  --run-id competition_batch_run \
  --identity-policy tiered_website_identity_v1 \
  --workers 6 \
  --max-per-host 2
```

### High-Scale 1,000-Company Execution (Frozen Universe Snapshot)
When evaluating the full 1,000-company evaluation sample using the frozen registry snapshot:
```bash
python scripts/run_competition_batch.py \
  --organisations data/random_1000_orgs.jsonl \
  --bulk data/signalpost-company-universe-2025.jsonl.gz \
  --output out/submission_1000_envelopes.jsonl \
  --profiles-output out/submission_1000_profiles.jsonl \
  --report out/submission_1000_report.json \
  --run-id competition_1000_run \
  --identity-policy tiered_website_identity_v1 \
  --workers 12 \
  --max-per-host 2
```

---

## 3. Verified 100-Company Smoke Test Results

Executed and verified against [`results/submission/`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/results/submission) under policy `tiered_website_identity_v1`:

| Metric / Dimension | Value | Target / Requirement | Verification Status |
| :--- | :---: | :---: | :---: |
| **Input Organisations** | **100** | Exactly 100 entities | **PASSED** |
| **Emitted Terminal Envelopes** | **100** | Exactly 100 envelopes | **PASSED** |
| **Dropped / Missing Entities** | **0** | Exactly 0 dropped | **PASSED** |
| **Duplicate Organisations** | **0** | 100 unique organisation numbers | **PASSED** |
| **Contract Schema Conformance**| **100%** | Full conformance to `OUTPUT_CONTRACT.md` | **PASSED** |
| **Terminal State Consistency** | **100%** | Every envelope has valid terminal status | **PASSED** |
| **Claims Emitted per Company** | **13** | Core identity, financials, roles, website, locations | **PASSED** |
| **Website Verification Yield** | **24 / 100 (24.0%)** | Zero wrong-company attributions | **VERIFIED** |
| **Website Tier Distribution** | **Tier A: 3 \| Tier B: 6 \| Tier C: 15** | Valid multi-tier evidence | **VERIFIED** |
| **Anti-Collision Protection** | **2 Conflicting Entities Blocked** | `Gyldendal ASA` & `Assist Ski AS` | **VERIFIED** |
| **Watchdog Compliance** | **155.69s / 2700s (5.8% of time budget)** | Hard cap: 45 minutes | **PASSED** |
| **Third-Party API Cost** | **$0.00** | $0.00 cost limit | **PASSED** |

---

## 4. Verification & Regression Test Suite

Hermetic test execution verifies zero offline regressions across 152 distinct test cases:

```powershell
.\.venv\Scripts\pytest.exe -q
```
**Result:** `152 passed, 5 subtests passed in 4.35s` (0 failures, 0 skips, 100% hermetic).

---

## 5. Submission Artifact Inventory

The submission package in [`results/submission/`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/results/submission) contains:

1. [`smoke_envelopes.jsonl`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/results/submission/smoke_envelopes.jsonl): 100 canonical output envelopes strictly conforming to `OUTPUT_CONTRACT.md`.
2. [`smoke_profiles.jsonl`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/results/submission/smoke_profiles.jsonl): 100 enriched company profiles with complete evidence graphs, cryptographic content hashes, and identity assessment records.
3. [`smoke_report.json`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/results/submission/smoke_report.json): Execution audit report, operational metrics, watchdog timer events, and validation checks.
4. [`submission_checklist.md`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/results/submission/submission_checklist.md): This authoritative submission checklist.
