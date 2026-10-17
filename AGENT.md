# Signalpost Atlas — Agent Architecture & Operational Policy

**System Version:** Signalpost Atlas 1.0  
**Competition:** Signalpost: Build an Agent That Finds Company Information (Builderr.ai)  

---

## 1. Research Pipeline Architecture

The Signalpost Atlas pipeline operates in deterministic, auditable stages:

```
[Input Org Numbers]
         │
         ▼
[1. Official Brreg Anchor]
  ├── Enhetsregisteret (Live / Bulk NLOD 2.0)
  ├── Regnskapsregisteret (Annual Accounts & Filing Years)
  ├── Official Roles (CEO, Board Members, Auditor)
  └── Subunits / Underenheter (Registered Workplaces)
         │
         ▼
[2. Verified Website Discovery & Identity Gate]
  ├── Registry Hjemmeside (Validated with SSRF check)
  ├── Norwegian Candidate Domains (.no heuristics)
  ├── Search Discovery (Brave Search API transient mode)
  └── Strict Identity Gate (Org number footer check / Legal name tokens)
         │
         ▼
[3. External Evidence Extraction]
  ├── Company Descriptions (Industry label, Meta descriptions, Trafilatura)
  ├── Public Contact Details (Mailto, Tel, Postal addresses)
  ├── Registered Locations (Subunits)
  ├── Leadership Roles & Management
  ├── Financial Statements (Revenue, Operating Result, Net Profit, Debt, Assets)
  └── Social Channels (Facebook, LinkedIn, Instagram, YouTube)
         │
         ▼
[4. Canonical Contract Serialization & Watchdog]
  ├── OUTPUT_CONTRACT.md Schema Generation
  ├── Bounded Concurrency & Per-Request Timeouts
  ├── Global Watchdog (45-min budget wind-down)
  ├── Centralized Run Persistence (results/runs/)
  └── Terminal Validation (Zero dropped rows)
```

---

## 2. Source-Selection Policy

1. **Tier 1 (Authoritative Official Records):**
   - Brønnøysundregistrene open APIs and bulk snapshots (licensed under NLOD 2.0).
   - Authoritative for legal name, organisation number, legal form, registered employees, official roles, workplaces, and filed financial statements.
2. **Tier 2 (Company-Owned Digital Assets):**
   - Verified official website, sitemaps, homepage, contact pages, about pages.
   - Authoritative for descriptions, direct contact emails, telephone numbers, and company-owned social handles.
3. **Tier 3 (Permitted Public APIs & Search):**
   - Brave Search API for candidate domain generation. All raw search titles, snippets, and queries are transient and discarded.
4. **Prohibited / Quarantined Sources:**
   - Direct web scraping of LinkedIn, Meta (Facebook/Instagram), Glassdoor, Indeed, X/Twitter, or TikTok is strictly prohibited by competition policy. Unofficial scrapers (e.g. JobSpy, guest scrapers) are quarantined and excluded from official runs.

---

## 3. Strict Identity Verification Gate

A candidate website or social profile is never accepted based on name similarity alone:

- **Primary Proof (1.0 Confidence):** Matching 9-digit Norwegian organisation number found verbatim in page text, footer, impressum, or privacy policy.
- **Secondary Proof (0.95 Confidence):** All distinctive legal-name tokens appear together in page title/header with substantive text (>= 100 characters) matching the registered municipality or address.
- **Immediate Rejection:**
  - Parked domains and hosting landing pages ("domain for sale", "parked at", "her flytter snart").
  - Aggregators and directories (`proff.no`, `purehelp.no`, `1881.no`, `gulesider.no`, etc.).
  - Parent/subsidiary mismatches (an operating company's site is not attributed to a separate business sports club or unrelated entity).

---

## 4. Evidence Integrity & Provenance

Every published fact is backed by an auditable evidence record containing:
- `id`: Unique identifier (e.g., `ev-1`).
- `source_url`: Verifiable URL where the document was retrieved.
- `source_class`: Classification (`official_registry`, `official_annual_accounts`, `official_roles`, `company_owned`).
- `retrieved_at`: ISO-8601 UTC timestamp.
- `content_sha256`: SHA-256 hash of the exact retrieved content.
- `claim_span`: The verbatim text fragment or source row key proving the claim.

No facts, URLs, dates, or financial metrics are ever hallucinated. Missing values remain explicitly `not_available` and are never replaced with zero.

---

## 5. Terminal States & Semantics

Every queried company returns exactly one terminal envelope with fields mapped to standard availability states:
- `available`: Field was discovered and verified for the exact legal entity.
- `not_available`: Source was checked systematically, but no record exists.
- `blocked`: Source refused or rate-limited requests (e.g. robots exclusion).
- `not_applicable`: Field is legally not relevant to this entity form.
- `ambiguous`: Candidate found, but identity confidence is below threshold.
- `failed`: An unrecoverable processing error occurred.

---

## 6. Global Watchdog & Resource Limits

- **Total Runtime Limit:** 45 minutes (2,700s). The watchdog monitors elapsed time and begins graceful wind-down 60 seconds before cutoff, finalizing all pending profiles.
- **Outbound Request Ceiling:** 2,000 requests per 1,000 companies (~2.0 req/company). Request budget is centrally counted and stops optional crawling before breaching limits.
- **API Cost Budget:** < $10.00. The default pipeline runs at $0.00 third-party cost.
