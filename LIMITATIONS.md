# Signalpost Atlas — System Limitations & Risk Assessment

**Date:** October 2026  
**Status:** Maintained for Signalpost Competition Submission  

---

## 1. Source Availability & Access Boundaries

1. **Restricted Social & Job Platforms:**
   - LinkedIn, Meta (Facebook/Instagram), Glassdoor, and Indeed do not permit unauthorized direct crawling under their terms of service.
   - Signalpost Atlas **only** extracts company-owned links and verified handles directly exposed on the company's verified website. Direct unauthenticated platform scraping is strictly excluded.
2. **Brreg Regnskapsregisteret Coverage Limits:**
   - Official annual accounts are legally required for limited companies (AS, ASA), but not for many sole proprietorships (ENK) or non-obliged entities. An HTTP 404 from the account endpoint reflects no statutory filing, properly mapped to `not_available` or `not_applicable`.
3. **Historical Account PDF Rate Limits:**
   - The historical filing copies endpoint (`/aarsregnskap/kopi/{org}/aar`) enforces an observed limit of ~30 requests per minute. Signalpost Atlas includes a reservation lock (`_reserve_history_slot`) to prevent rate-limit penalties.

---

## 2. Identity Resolution & Ambiguity Edge Cases

1. **Umbrella & Holding Companies:**
   - Many Norwegian entities are holding companies (`AS`, `Holding AS`) that share a registered address and management with operating subsidiaries, but do not maintain a separate consumer website.
   - Signalpost Atlas strictly requires the distinctive legal name or exact organisation number on the website. If only a parent portfolio page is found, the agent abstains (`ambiguous` / `not_available`) rather than risking wrong-company match disqualification.
2. **Parked Domains & Expired Registrations:**
   - Companies that have ceased active operations or allowed their domain registration to lapse often resolve to hosting landing pages or domain brokers (e.g. HugeDomains, Miss Hosting). The agent detects parked domain text patterns and excludes them (`score = 0.1`).

---

## 3. Resource & Operational Limits

1. **Request Budget:**
   - Hard capped at 2,000 outbound HTTP requests per 1,000-company run.
   - If an evaluation batch contains companies with slow or failing websites, the watchdog throttles deep secondary page crawls to stay within budget.
2. **Execution Time:**
   - Hard capped at 45 minutes (2,700 seconds).
   - Monitored by the global watchdog, ensuring graceful finalization with zero lost records.
3. **API Cost:**
   - Configured for $0.00 declared third-party cost by default using open NLOD 2.0 Brreg records and direct website crawling.

---

## 4. Unsupported Fields & Safe Abstention

The following fields cannot be verified with durable public evidence and are safely classified as `not_available` or unsupported:
- Real-time hiring velocity / headcount changes without authorized LinkedIn Recruiter API access.
- Private employee review sentiment (Glassdoor/Indeed) without licensed commercial data feeds.
- Fabricated or extrapolated revenue projections.
