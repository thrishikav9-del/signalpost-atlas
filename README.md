# Signalpost Atlas

**Signalpost Atlas** is an evidence-first, deterministic Norwegian company intelligence agent built for the [Builderr.ai Signalpost Challenge](https://builderr.ai/challenges/signalpost) (*"Build an Agent That Finds Company Information"*).

Starting from a 9-digit Norwegian organisation number, the agent anchors company identity in authoritative registry filings (Brønnøysundregistrene), discovers and strictly verifies official company websites, extracts audited financial filings, leadership roles, and registered subunit locations, and compiles complete, evidence-backed company profiles strictly conforming to `OUTPUT_CONTRACT.md`.

---

## 1. Key Features

- **Authoritative Statutory Anchoring:** Integrates Brønnøysundregistrene Enhetsregisteret, Regnskapsregisteret, Roller, and Underenheter under Norwegian Licence for Open Government Data (NLOD 2.0). Supports live REST API hydration and offline universe snapshots (`data/signalpost-company-universe-2025.jsonl.gz`).
- **Cryptographic Provenance:** Every claim is tied to an explicit `evidence_id` carrying a 64-character SHA-256 content hash, UTC retrieval timestamp, and authoritative source URL.
- **Tiered Website Identity Gating:** Enforces conservative three-tier identity verification (`tiered_website_identity_v1`):
  - *Tier A:* Verbatim 9-digit Norwegian organisation number found in captured page text.
  - *Tier B:* Distinctive legal-name tokens matching title/H1 and registered physical street address or postal code.
  - *Tier C:* Registry-linked domain matching distinctive legal-name tokens and registered municipality/locality.
  - Negative filters and collision guards quarantine parent groups, parked pages, and subsidiary mismatches.
- **Currency-Safe Financial Extraction:** Verbatim ingestion of audited annual accounts from Regnskapsregisteret. Values are only placed into `*_nok` fields when the statutory filing was reported in NOK; foreign-currency filings (e.g. USD, EUR) are safely recorded with their reported currency and period, while NOK fields are marked `not_available` to prevent unverified FX rate conversion errors.
- **Boilerplate Description Rejection:** Automatically detects and filters CMS/WordPress template boilerplate (*"This is an example page... Hi there! I'm a bike messenger..."*), falling back to verified corporate slogans or registry industry descriptions.
- **Source Policy Compliance:** Completely abstains from scraping prohibited platforms (LinkedIn, Meta, Glassdoor, Indeed). Strictly respects target domain `robots.txt` and rate limits ($\le 2$ connections per host).
- **Request & Runtime Governance:** Built-in central governor enforces the competition's 2,000-request ceiling and 45-minute (2,700s) wall-clock deadline with graceful wind-down.
- **Zero API Cost:** Operates at **$0.00 USD** external API cost. No paid search or LLM APIs are required.

---

## 2. System Architecture

```
Input File (JSON / JSONL / TXT — 9-digit Norwegian Org Numbers)
              │
              ▼
[1. Official Brreg Anchor]
  ├── Enhetsregisteret (Live REST API or Frozen Universe Snapshot)
  ├── Regnskapsregisteret (Audited Annual Accounts & Currency Check)
  ├── Official Roles (Board of Directors & Executive Management)
  └── Underenheter (Registered Subunits & Branch Locations)
              │
              ▼
[2. Verified Website Discovery & Identity Gate]
  ├── Registry-declared Hjemmeside & Candidate Domains
  ├── Tiered Identity Filter (Tier A: OrgNr | Tier B: Address | Tier C: Registry+Locality)
  └── Anti-Collision Safeguards (Parked Domains & Group Collisions Blocked)
              │
              ▼
[3. External Evidence Extraction]
  ├── Substantive Business Description (Boilerplate Filtered)
  ├── Contact Coordinates (Verified mailto / tel)
  └── Verified Social Handles (Quarantined if unverified)
              │
              ▼
[4. Canonical Contract Serialization & Watchdog]
  ├── OUTPUT_CONTRACT.md Canonical Envelopes (6 Availability States)
  ├── Atomic JSONL Writing & Resume Checkpointing
  └── Centralized Telemetry & Verification Reporting
```

---

## 3. Requirements

- **Python:** Python 3.12 or newer (tested and verified on Python 3.13.5).
- **Operating System:** Windows, Linux, or macOS.
- **Dependencies:** `beautifulsoup4`, `extruct`, `lxml`, `pydantic`, `pypdf`, `tldextract`, `trafilatura`.
- **Development Dependencies:** `pytest`.

---

## 4. Installation

### Windows (PowerShell)

```powershell
# 1. Clone repository
git clone https://github.com/thrishikav9-del/signalpost-atlas.git
cd signalpost-atlas

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Install editable package with test dependencies
pip install -e ".[dev]"
```

### Linux / macOS

```bash
# 1. Clone repository
git clone https://github.com/thrishikav9-del/signalpost-atlas.git
cd signalpost-atlas

# 2. Create virtual environment
python3 -m venv .venv

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install editable package with test dependencies
pip install -e ".[dev]"
```

---

## 5. Run the Agent

The competition entrypoint is [`scripts/run_competition_batch.py`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/scripts/run_competition_batch.py).

### 1. Run 100-Company Evaluation Batch

Run the agent across the verified 100-company evaluation sample (`results/test_reports/smoke_100_orgs.jsonl`):

**Windows (PowerShell):**
```powershell
python scripts/run_competition_batch.py `
  --organisations results/test_reports/smoke_100_orgs.jsonl `
  --output out/smoke_100_envelopes.jsonl `
  --profiles-output out/smoke_100_profiles.jsonl `
  --report out/smoke_100_report.json `
  --run-id smoke_100_eval `
  --identity-policy tiered_website_identity_v1 `
  --workers 6 `
  --max-per-host 2
```

**Linux / macOS:**
```bash
python scripts/run_competition_batch.py \
  --organisations results/test_reports/smoke_100_orgs.jsonl \
  --output out/smoke_100_envelopes.jsonl \
  --profiles-output out/smoke_100_profiles.jsonl \
  --report out/smoke_100_report.json \
  --run-id smoke_100_eval \
  --identity-policy tiered_website_identity_v1 \
  --workers 6 \
  --max-per-host 2
```

### 2. Run 1,000-Company Evaluation Batch

Run across the repository's 1,000-company manifest (`data/random_1000_orgs.jsonl`):

**Windows (PowerShell):**
```powershell
python scripts/run_competition_batch.py `
  --organisations data/random_1000_orgs.jsonl `
  --output out/submission_1000_envelopes.jsonl `
  --profiles-output out/submission_1000_profiles.jsonl `
  --report out/submission_1000_report.json `
  --run-id competition_1000_batch `
  --identity-policy tiered_website_identity_v1 `
  --workers 12 `
  --max-per-host 2
```

**Linux / macOS:**
```bash
python scripts/run_competition_batch.py \
  --organisations data/random_1000_orgs.jsonl \
  --output out/submission_1000_envelopes.jsonl \
  --profiles-output out/submission_1000_profiles.jsonl \
  --report out/submission_1000_report.json \
  --run-id competition_1000_batch \
  --identity-policy tiered_website_identity_v1 \
  --workers 12 \
  --max-per-host 2
```

### 3. Optional Bulk Snapshot Acceleration

To eliminate live HTTP requests for registry lookups, provide the frozen universe snapshot (`data/signalpost-company-universe-2025.jsonl.gz`), or an external Brreg bulk CSV dump (`enheter_alle.csv.gz` from Brønnøysundregistrene open data):

```powershell
python scripts/run_competition_batch.py `
  --organisations data/random_1000_orgs.jsonl `
  --bulk data/signalpost-company-universe-2025.jsonl.gz `
  --output out/submission_1000_envelopes.jsonl `
  --profiles-output out/submission_1000_profiles.jsonl `
  --report out/submission_1000_report.json `
  --run-id competition_1000_snapshot `
  --identity-policy tiered_website_identity_v1 `
  --workers 12 `
  --max-per-host 2
```

### 4. Resuming an Interrupted Batch

If a batch execution is interrupted, append `--resume` to resume from the last saved checkpoint without repeating completed companies:

```powershell
python scripts/run_competition_batch.py `
  --organisations results/test_reports/smoke_100_orgs.jsonl `
  --output out/smoke_100_envelopes.jsonl `
  --profiles-output out/smoke_100_profiles.jsonl `
  --report out/smoke_100_report.json `
  --run-id smoke_100_eval `
  --resume
```

---

## 6. Run Tests

The repository includes a complete hermetic regression and unit test suite (zero network calls, zero external API dependencies):

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\python -m pytest -v
```

**Linux / macOS:**
```bash
pytest -v
```

### Observed Test Results
- **Status:** **159 passed in ~4–8s** (100% hermetic pass, 0 failures, 0 skips).
- **Test Modules:**
  - `tests/test_cache.py`: 4 tests (caching & single-flight)
  - `tests/test_concurrency.py`: 10 tests (worker pools & rate limiters)
  - `tests/test_currency_and_boilerplate.py`: 7 tests (foreign currency & template text rejection)
  - `tests/test_identity_regression.py`: 12 tests (identity edge cases & collision guards)
  - `tests/test_poc.py`: 104 tests (core entity normalization, parsing & screening)
  - `tests/test_snapshot.py`: 4 tests (snapshot streaming & bulk ingestion)
  - `tests/test_tiered_identity.py`: 18 tests (tiered verification rules A/B/C)

---

## 7. Input and Output Formats

### Supported Input Formats
Input files passed to `--organisations` can be formatted as:
1. **JSONL:** `{"organisation_number": "923609016"}`
2. **JSON Array:** `[{"organisation_number": "923609016"}, ...]`
3. **Plain Text:** Newline-delimited 9-digit numbers (`923609016\n...`)

### Output Envelope Schema (`OUTPUT_CONTRACT.md`)
Each input organisation number produces **exactly one** terminal JSON envelope:

```json
{
  "organisation_number": "923609016",
  "run": {
    "run_id": "smoke_100_verified",
    "started_at": "2026-10-17T16:32:06.745337Z",
    "completed_at": "2026-10-17T16:39:09.893128Z",
    "terminal_status": "completed"
  },
  "claims": [
    {
      "field": "legal_name",
      "value": "EQUINOR ASA",
      "availability": "available",
      "confidence": 1.0,
      "evidence_ids": ["ev-1"]
    },
    {
      "field": "official_website",
      "value": "https://www.equinor.com/",
      "availability": "available",
      "confidence": 0.95,
      "evidence_ids": ["ev-2"]
    },
    {
      "field": "annual_revenue_nok",
      "value": null,
      "reporting_period": {"fraDato": "2023-01-01", "tilDato": "2023-12-31"},
      "reported_currency": "USD",
      "availability": "not_available",
      "confidence": 1.0,
      "evidence_ids": ["ev-3"]
    }
  ],
  "evidence": [
    {
      "id": "ev-1",
      "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/923609016",
      "source_class": "official_registry_live",
      "retrieved_at": "2026-10-17T16:32:06.764875Z",
      "content_sha256": "4b97d25e...",
      "claim_span": "registry_live"
    }
  ],
  "changes": [],
  "errors": [],
  "operations": {
    "requests": 10,
    "runtime_ms": 4233,
    "third_party_cost_usd": 0.0
  }
}
```

### Allowed Availability States
Adheres strictly to `OUTPUT_CONTRACT.md`:
- `available`: Verified with authoritative evidence for the exact legal entity.
- `not_available`: Source checked systematically; no record exists, or foreign currency filing cannot be safely represented in `*_nok` without FX conversion.
- `blocked`: Source rate-limited, blocked access, or anti-collision guard triggered.
- `not_applicable`: Field legally does not apply to this entity type.
- `ambiguous`: Candidate exists, but exact-entity identity proof is inconclusive.
- `failed`: Processing error encountered during fetch.

---

## 8. Existing Benchmark Evidence and Limitations

### Measured Benchmark Runs

The repository contains empirical records for the following historical runs:

| Benchmark Run | Batch Size | Total Requests | Runtime (s) | Req / Co | Time / Co | Terminal Status | Valid Envelopes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Level A Baseline** | 10 | 151 | 71.68 s | 15.10 | 7.17 s | 10 / 10 | 100% compliant |
| **Level B Optimized** | 50 | 360 | 186.98 s | 7.20 | 3.74 s | 50 / 50 | 100% compliant |
| **Fresh Smoke Run** | 100 | 1,030 | 423.31 s | 10.30 | 4.23 s | 100 / 100 | 100% compliant |

### Forensic Accuracy Audit Findings (100-Company Verification Set)
Audited against independent ground truth in [`results/submission/final_accuracy_audit.json`](file:///c:/Users/thris/OneDrive/Documents/iit%20bhu/ppt/signalpost-atlas/results/submission/final_accuracy_audit.json):
- **Output Validity:** **100 / 100 (100.00%)** valid terminal envelopes emitted (0 dropped, 0 duplicate).
- **Confirmed Website Identity Precision:** **27 / 27 (100.00%)** confirmed websites independently verified against target legal entities (**0 material false positives**).
- **Claim Precision (Positive Claims):** **1,079 / 1,079 (100.00%)** verified correct.
- **Company Exact Match (All Fields):** **100 / 100 (100.00%)** companies have all audited claims verified correct.
- **Fabricated Financial Values:** **0** (Zero). All figures match official filings in Regnskapsregisteret verbatim.
- **Foreign Currency Safety:** 13 companies filing in USD or EUR are safely marked `not_available` in `*_nok` fields to prevent unit mismatch errors.
- **Website Discovery Recall:** **NOT MEASURABLE** (The ground-truth denominator of companies with live websites across the 100 sample is not established; assuming undiscovered = nonexistent is prohibited).
- **Official Competition Score:** **OFFICIAL BUILDERr SCORE: NOT MEASURABLE FROM AVAILABLE TOOLS** (No automated external scorer was provided in the challenge pack; points out of 100 are not manufactured).

---

## 9. Competition Constraints and Source Policy

- **Daily Limits:** 45 minutes wall-clock time, 2,000 outbound HTTP requests, $10.00 declared external API cost.
- **Observed 100-Company Resource Usage:** 7.06 minutes runtime (15.7% of deadline), 1,030 requests (51.5% of quota), $0.00 third-party cost.
- **Prohibited Platforms:** Signalpost Atlas explicitly filters out and forbids scraping of LinkedIn, Meta (Facebook/Instagram), Glassdoor, and Indeed.
- **Robots.txt & Rate Limiting:** All outbound HTTP requests strictly adhere to target domain `robots.txt` rules and enforce domain-level concurrency locks.
- **Zero Hallucination:** If a metric or website cannot be independently corroborated with evidence, it is emitted with explicit status `not_available` or `ambiguous` rather than synthesized.

---

## 10. Repository Structure

```
signalpost-atlas/
├── README.md                                     # Project documentation and instructions
├── OUTPUT_CONTRACT.md                            # Canonical output contract specification
├── DATA_SCHEMA.md                                # Input/output schema and field definitions
├── LIMITATIONS.md                                # System boundaries and safe abstentions
├── pyproject.toml                                # Pinned project dependencies and config
├── data/
│   ├── random_1000_orgs.jsonl                    # 1,000 sampled Norwegian organisation numbers
│   ├── signalpost-company-universe-2025.jsonl.gz  # 411,160-entity frozen registry snapshot
│   └── universe-metadata.json                    # Universe sampling and stratum metadata
├── results/
│   ├── submission/
│   │   ├── verified_smoke_envelopes.jsonl        # 100 verified canonical output envelopes
│   │   ├── fresh_smoke_profiles.jsonl            # 100 researched profiles with evidence graph
│   │   ├── verified_smoke_report.json            # Execution metrics & watchdog report
│   │   ├── final_accuracy_audit.json             # Machine-readable forensic audit metrics
│   │   ├── final_accuracy_audit.md               # Comprehensive forensic audit report
│   │   ├── final_claim_verification.jsonl        # 1,290 claim-level audit records
│   │   ├── final_identity_verification.jsonl     # 100 company-level identity audit records
│   │   └── submission_checklist.md               # Final submission checklist
│   └── test_reports/
│       └── smoke_100_orgs.jsonl                  # Official 100-company smoke test input
├── scripts/
│   ├── run_competition_batch.py                  # Primary competition batch entrypoint
│   └── score_competition_v3.py                   # Internal development heuristic (proxy only)
├── src/norway_company_agent/
│   ├── batch.py                                  # Batch hydration & envelope formatting
│   ├── canonical_contract.py                     # Contract serialization & currency safeguards
│   ├── identity.py                               # Tiered website identity verification
│   ├── official.py                               # Brreg API & data normalization
│   ├── website.py                                # Direct HTTP crawling & robots.txt handling
│   └── ...
└── tests/
    ├── test_cache.py                             # HTTP caching & single-flight tests
    ├── test_concurrency.py                       # Concurrency & request budget tests
    ├── test_currency_and_boilerplate.py          # Currency integrity & boilerplate rejection
    ├── test_identity_regression.py               # Identity edge cases & collision guards
    ├── test_poc.py                               # Core entity normalization & screening
    ├── test_snapshot.py                          # Snapshot streaming & bulk ingestion
    └── test_tiered_identity.py                   # Tiered verification rules (Tiers A/B/C)
```

---

## 11. License and Data Attribution

- **Software License:** MIT License for Signalpost Atlas codebase.
- **Data Source Attribution:** Registry data is acquired under the Norwegian Licence for Open Government Data (NLOD 2.0) from [Brønnøysundregistrene](https://data.brreg.no/).
