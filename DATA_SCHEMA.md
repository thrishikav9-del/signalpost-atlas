# Signalpost Atlas — Data Schema Specification

This document details the exact input, output, claim, and evidence schemas used by the Signalpost Atlas agent, adhering to `OUTPUT_CONTRACT.md` and the official Builderr evaluation harness.

---

## 1. Input Schema

The input is provided as a JSON, JSONL, or newline-delimited text file.

### JSONL Input Example
```json
{"organisation_number": "923609016"}
{"organisation_number": "940729092", "evaluation_split": "held_out", "sample_slice": "stress"}
```

- `organisation_number` (string, required): Exactly 9 Norwegian digits.
- `evaluation_split` (string, optional): Evaluator partition (`held_out`, `train`, `benchmark`).
- `sample_slice` (string, optional): Stratum metadata.

---

## 2. Output Envelope Schema (`OUTPUT_CONTRACT.md`)

Each input organisation number produces **exactly one** terminal JSON object.

```json
{
  "organisation_number": "923609016",
  "run": {
    "run_id": "level_a_10_test",
    "started_at": "2026-10-15T15:11:45.420518Z",
    "completed_at": "2026-10-15T15:12:57.100927Z",
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
      "value": 1120000000000.0,
      "reporting_period": "2025",
      "currency": "NOK",
      "availability": "available",
      "confidence": 1.0,
      "evidence_ids": ["ev-3"]
    }
  ],
  "evidence": [
    {
      "id": "ev-1",
      "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/923609016",
      "source_class": "official_registry",
      "retrieved_at": "2026-10-15T15:11:48.000000Z",
      "content_sha256": "4b97d25e...",
      "claim_span": "923609016"
    },
    {
      "id": "ev-2",
      "source_url": "https://www.equinor.com/",
      "source_class": "company_owned",
      "retrieved_at": "2026-10-15T15:12:02.000000Z",
      "content_sha256": "fc346476...",
      "claim_span": "Equinor ASA"
    }
  ],
  "changes": [],
  "errors": [],
  "operations": {
    "requests": 15,
    "runtime_ms": 71680,
    "third_party_cost_usd": 0.0
  }
}
```

---

## 3. Allowed Availability States

| State | Semantic Meaning | Usage Rule |
|---|---|---|
| `available` | Found and verified with evidence for exact company | Field `value` must be populated and non-null |
| `not_available` | Checked source systematically; no data exists | Field `value` is `null` (never converted to 0) |
| `blocked` | Source refused access (403, 429, WAF, robots exclusion) | Field `value` is `null` |
| `not_applicable` | Field does not apply to this entity type | Field `value` is `null` |
| `ambiguous` | Discovered candidate lacks exact-entity confidence | Field `value` is `null` |
| `failed` | Processing error encountered during fetch | Field `value` is `null` |

---

## 4. Supported Information Families

1. **Official Legal Identity:** `legal_name`, `legal_form`, `registered_employees`, `registered_municipality`.
2. **Company Online Footprint:** `official_website`, `company_description`, `official_social_channels`.
3. **Official Financials:** `annual_revenue_nok`, `operating_profit_nok`, `net_annual_profit_nok`, `total_assets_nok`, `total_debt_nok`, `total_equity_nok`.
4. **Leadership & People:** `leadership_roles` (list of active roles with role titles and person names).
5. **Workplaces & Locations:** `registered_locations` (list of registered subunits with addresses and employee counts).

---

## 5. Validation Rules
- **Completeness:** Every input organisation number has exactly one output envelope.
- **Uniqueness:** No duplicate organisation numbers in output.
- **Evidence Integrity:** Every claim references at least one valid evidence record ID.
- **SHA-256 Hashes:** Every evidence item must provide the genuine SHA-256 content hash of the retrieved source.
