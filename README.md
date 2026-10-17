# Signalpost Atlas

**Signalpost Atlas** is an evidence-first, deterministic Norwegian company intelligence agent built for the [Builderr.ai Signalpost Challenge](https://builderr.ai/challenges/signalpost) ("Build an Agent That Finds Company Information").

Starting from a 9-digit Norwegian organisation number, the agent anchors company identity in authoritative registry filings (Brønnøysundregistrene), discovers and strictly verifies official company websites, extracts audited financial filings, leadership roles, and registered subunit locations, and compiles complete, evidence-backed company profiles strictly conforming to `OUTPUT_CONTRACT.md`.

---

## Key Capabilities

- **Authoritative Identity Anchoring:** Integrates Brønnøysundregistrene Enhetsregisteret, Regnskapsregisteret, Roller, and Underenheter under NLOD 2.0 open data terms. Supports both live REST APIs and offline frozen bulk snapshots (`enheter_alle.csv.gz`).
- **Cryptographic Provenance:** Every claim is tied to an explicit `evidence_id` carrying a 64-character SHA-256 content hash, retrieval timestamp, and authoritative source URL.
- **Strict Identity Gating:** Enforces conservative multi-token and exact 9-digit organisation number matching on candidate homepages. Quarantines parent group domains, parked placeholder pages, and subsidiary mismatches.
- **Audited Financial History:** Ingests official annual accounts directly from Regnskapsregisteret with mandatory statutory reporting periods and ISO NOK currency. Zero hallucination, zero fabricated numbers.
- **Source Policy Compliance:** Completely abstains from scraping prohibited platforms (LinkedIn, Meta, Glassdoor, Indeed). Strictly respects robots.txt and domain rate limits.
- **Adaptive Request Budget Governor:** Guarantees strict compliance with the competition's 2,000-request and 45-minute caps through adaptive module shedding and streaming CSV ingestion.
- **Zero Third-Party Cost:** Operates at **$0.00** declared API cost. No paid LLM or search APIs are required.

---

## System Architecture

```
Input File (JSON / JSONL / TXT)
              │
              ▼
[1. Official Brreg Anchor]
  ├── Enhetsregisteret (Live REST API or Frozen Bulk CSV)
  ├── Regnskapsregisteret (Audited Annual Accounts)
  ├── Official Roles (Board & Executive Management)
  └── Underenheter (Registered Subunits & Branches)
              │
              ▼
[2. Verified Website Discovery & Identity Gate]
  ├── Registry-declared Hjemmeside & Candidate Domains
  ├── Strict Identity Filter (Score 1.00 Org Match / Score 0.95 Name Match)
  └── Negative Filter (Parked Domains, Group Mismatches Quarantined)
              │
              ▼
[3. External Evidence Extraction]
  ├── Substantive Business Activity & Description
  ├── Contact Coordinates (Verified mailto / tel)
  └── Gated Social Handles (Parent handles quarantined)
              │
              ▼
[4. Canonical Contract Serialization & Watchdog]
  ├── OUTPUT_CONTRACT.md Canonical Envelopes
  ├── Atomic JSONL Writing & Resume Checkpointing
  └── Centralized Metrics & Reporting (results/reports/)
```

---

## Installation & Clean-Machine Setup

Requires **Python 3.12+** (tested and verified on Python 3.13.5).

```bash
# 1. Clone repository
git clone https://github.com/<your-username>/signalpost-atlas.git
cd signalpost-atlas

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 4. Install editable package with test dependencies
pip install -e ".[dev]"
```

---

## Execution Modes & Exact Commands

### 1. Run Automated Test Suite (121 Tests)
Verify installation and regression suite (passes in under 5 seconds):
```bash
pytest -v
```

### 2. Run Official Smoke Test (100 Companies)
Run the agent across the official 100-company evaluation sample:
```bash
python scripts/run_competition_batch.py \
  --organisations results/test_reports/smoke_100_orgs.jsonl \
  --output out/smoke_100_envelopes.jsonl \
  --profiles-output out/smoke_100_profiles.jsonl \
  --report out/smoke_100_report.json \
  --run-id smoke-100-eval
```

### 3. Run with Frozen Bulk Registry Snapshot (Target 1,000-Company Architecture)
When using the official Brønnøysund bulk snapshot (`enheter_alle.csv.gz`), registry lookups consume **0 HTTP requests**:
```bash
python scripts/run_competition_batch.py \
  --organisations data/test_1000_orgs.jsonl \
  --bulk data/enheter_alle.csv.gz \
  --output out/submission_envelopes.jsonl \
  --report out/submission_report.json \
  --run-id full-batch-1000
```

### 4. Resuming an Interrupted Batch
If an execution is stopped, resume immediately without repeating completed companies:
```bash
python scripts/run_competition_batch.py \
  --organisations results/test_reports/smoke_100_orgs.jsonl \
  --output out/smoke_100_envelopes.jsonl \
  --profiles-output out/smoke_100_profiles.jsonl \
  --report out/smoke_100_report.json \
  --run-id smoke-100-eval \
  --resume
```

---

## Empirical Benchmark Results

Measured empirical results across all verified benchmark runs:

| Benchmark Run | Entities | Requests | Runtime (s) | Req / Co | Time / Co | Terminal Status | Output Validity |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Level A Baseline** | 10 | 151 | 71.68 s | 15.10 | 7.17 s | 10/10 (100%) | 100% compliant |
| **Level B Optimized** | 50 | 360 | 186.98 s | 7.20 | 3.74 s | 50/50 (100%) | 100% compliant |
| **Official Smoke Run** | 100 | 770 | 441.95 s | 7.70 | 4.42 s | 100/100 (100%) | 100% compliant |

---

## 1,000-Company Request Budget & Scaling Models

Under Builderr's competition rules, agents are capped at **2,000 total HTTP requests** and **45 minutes wall time**.

1. **Model A (Naive Unconstrained Live Crawl):**
   - $1,000 \times 7.70\text{ req/co} = \mathbf{7,700\text{ requests}}$ (385% of limit) $\rightarrow$ **FATAL DISQUALIFICATION (0/100)**.
2. **Model B (Governed Live API with Module Shedding):**
   - In live mode without a bulk snapshot, `RequestBudgetGovernor` caps outbound calls at **1,950 requests** by shedding secondary pages and subunits while preserving 100% of core identity, accounting obligations, and annual accounts.
3. **Model C (Snapshot-Backed Execution — Target Architecture):**
   - Using `--bulk data/enheter_alle.csv.gz`, registry queries consume **0 requests**, allowing full deep website crawls and secondary module enrichment within **1,950 requests**.

---

## Official Scoring Rubric vs. Internal Proxy Disclosure

> [!IMPORTANT]
> **Official Builderr Rubric (100 Points):**
> - **Recall & Coverage (50 points):** Completeness of legal identity, accounting obligations, financial history, verified websites, leadership roles, and locations.
> - **Precision & Evidence (30 points):** Cryptographic SHA-256 evidence anchoring, zero false company associations, and source compliance.
> - **Synthesis & Extensibility (12 points):** Deterministic refresh replay, atomic resumption, schema conformance, and clean terminal state handling.
> - **UX & Product Design (8 points):** Schema inspectability, minimal payload bloat, and operator clarity.
>
> **Note on `scripts/score_competition_v3.py`:**  
> This script is an internal development heuristic used during early prototyping and is **not the official evaluation engine**. Official scoring is determined exclusively by the competition evaluators.

---

## Source Policy & Legal Compliance

- **No Prohibited Platforms:** Signalpost Atlas explicitly filters out and forbids scraping of LinkedIn, Meta, Glassdoor, and Indeed.
- **Robots.txt & Rate Limiting:** All outbound HTTP requests strictly adhere to target domain robots.txt rules and maintain domain-level concurrency locks.
- **Open Data:** Registry data is acquired under the Norwegian Licence for Open Government Data (NLOD 2.0).
- **Zero Hallucination:** If a metric or website cannot be independently corroborated with evidence, it is emitted with explicit status `not_available` or `not_found` rather than synthesized.
