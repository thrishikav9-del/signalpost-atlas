"""
Regression tests for strict website identity gating policy (Phase E requirements).

Verifies the 10 mandatory rules:
1. A parent-group domain is not attributed to a subsidiary without sufficient evidence.
2. A shared global domain is not automatically attributed to a specific local legal entity.
3. A same-name but different company is rejected when its identifier/address conflicts.
4. A trading-name website remains ambiguous unless the required identity evidence passes.
5. An exact matching nine-digit identifier passes.
6. Legal-name tokens plus the correct registered postcode or street address pass.
7. An identifier belonging to a different company fails.
8. Blocked pages are never crawled in violation of robots.txt.
9. Score thresholds and decision rules cannot contradict each other.
10. Human review remains not_reviewed unless explicitly supplied by a person.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from norway_company_agent.canonical_contract import synthesize_claims_and_evidence
from norway_company_agent.identity import (
    apply_website_identity_gate,
    assess_social_identity,
    assess_website_identity,
)
from norway_company_agent.website import _robots_allowed, fetch_website


class StrictWebsiteIdentityRegressionTests(unittest.TestCase):
    # Rule 1: Parent-group domain is not attributed to subsidiary without sufficient evidence
    def test_1_parent_group_domain_not_attributed_to_subsidiary(self):
        subsidiary_profile = {
            "organisation_number": "981234567",
            "name": "Lyse Produksjon AS",
            "postcode": "4001",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.lyse.no/",
                        "title": "Lyse - Energi, fiber og underholdning",
                        "description": "Altibox og strøm til private og bedrifter",
                        "main_text_excerpt": "Lyse leverer strøm, internett og TV til over 100 000 kunder i Rogaland.",
                    },
                }
            },
        }
        assessment = assess_website_identity(subsidiary_profile)
        self.assertFalse(assessment["publishable"])
        self.assertEqual(assessment["status"], "ambiguous")
        self.assertEqual(assessment["automated_identity_result"], "insufficient_evidence")

    # Rule 2: Shared global domain is not automatically attributed to specific local legal entity
    def test_2_shared_global_domain_not_automatically_attributed_to_local_legal_entity(self):
        local_entity = {
            "organisation_number": "987111222",
            "name": "Siemens Healthcare AS",
            "postcode": "0277",
            "address": "Postboks 1",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.siemens.com/global",
                        "title": "Siemens Global Website",
                        "description": "Siemens is a technology company focused on industry and infrastructure.",
                        "main_text_excerpt": "Siemens technology is transforming the everyday for billions of people.",
                    },
                }
            },
        }
        assessment = assess_website_identity(local_entity)
        self.assertFalse(assessment["publishable"])
        self.assertEqual(assessment["status"], "ambiguous")
        self.assertIn("not all distinctive legal-name tokens match page title or H1", assessment["reasons"])

    # Rule 3: Same-name but different company is rejected when identifier or address conflicts
    def test_3_same_name_different_company_rejected_when_identifier_or_address_conflicts(self):
        target_company = {
            "organisation_number": "911222333",
            "name": "Nordic Transport AS",
            "postcode": "5003",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.nordictransport.no/",
                        "title": "Nordic Transport AS",
                        "main_text_excerpt": "Nordic Transport AS, Org.nr 999888777, Postboks 50, 7010 Trondheim",
                    },
                }
            },
        }
        assessment = assess_website_identity(target_company)
        self.assertFalse(assessment["publishable"])
        self.assertEqual(assessment["status"], "ambiguous")
        self.assertEqual(assessment["automated_identity_result"], "conflicting_identifier")

    # Rule 4: Trading-name website remains ambiguous unless required identity evidence passes
    def test_4_trading_name_website_remains_ambiguous_without_required_evidence(self):
        company = {
            "organisation_number": "922333444",
            "name": "Ola Hansen VVS AS",
            "postcode": "1337",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.bademiljo.no/",
                        "title": "Bademiljø - Din rørlegger",
                        "description": "Bademiljø leverer rørleggertjenester og baderom.",
                        "main_text_excerpt": "Velkommen til Bademiljø for kvalitet og rørleggerkompetanse.",
                    },
                }
            },
        }
        assessment = assess_website_identity(company)
        self.assertFalse(assessment["publishable"])
        self.assertEqual(assessment["status"], "ambiguous")

    # Rule 5: Exact matching nine-digit identifier passes
    def test_5_exact_matching_nine_digit_identifier_passes(self):
        company = {
            "organisation_number": "990918546",
            "name": "Scatec ASA",
            "postcode": "0277",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.scatec.com/en/",
                        "title": "Scatec - Improving the future",
                        "identity_text_excerpt": "Scatec ASA, Org. nr: 990 918 546, Askekroken 11, 0277 Oslo",
                        "main_text_excerpt": "Scatec is a leading renewable energy solutions provider.",
                    },
                }
            },
        }
        assessment = assess_website_identity(company)
        self.assertTrue(assessment["publishable"])
        self.assertEqual(assessment["status"], "exact")
        self.assertEqual(assessment["score"], 1.0)
        self.assertEqual(assessment["condition_passed"], "A_exact_org_number")
        self.assertEqual(assessment["automated_identity_result"], "exact_identifier")
        self.assertEqual(assessment["identity_evidence"]["matched_identifier"], "990918546")
        self.assertIn("990 918 546", assessment["identity_evidence"]["excerpt"])

    # Rule 6: Legal-name tokens plus correct registered postcode or street address pass
    def test_6_legal_name_tokens_plus_registered_postcode_or_street_address_passes(self):
        company = {
            "organisation_number": "912345678",
            "name": "Norsk Fiskeeksport AS",
            "postcode": "6002",
            "address": "Skansekaia 3",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.norskfiskeeksport.no/",
                        "title": "Norsk Fiskeeksport AS - Premium Seafood",
                        "description": "High quality seafood export from Norway",
                        "main_text_excerpt": "Velkommen til Norsk Fiskeeksport. Besøk oss på Skansekaia 3, 6002 Ålesund.",
                    },
                }
            },
        }
        assessment = assess_website_identity(company)
        self.assertTrue(assessment["publishable"])
        self.assertEqual(assessment["status"], "exact")
        self.assertEqual(assessment["score"], 0.95)
        self.assertEqual(assessment["condition_passed"], "B_name_plus_address")
        self.assertEqual(assessment["automated_identity_result"], "combined_identity")
        self.assertEqual(assessment["identity_evidence"]["matched_postcode"], "6002")

    # Rule 7: An identifier belonging to a different company fails
    def test_7_identifier_belonging_to_different_company_fails(self):
        company = {
            "organisation_number": "911111111",
            "name": "Alfa Logistikk AS",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.alfalogistikk.no/",
                        "title": "Alfa Logistikk AS",
                        "main_text_excerpt": "Alfa Logistikk AS, Org.nr: 922 222 222.",
                    },
                }
            },
        }
        assessment = assess_website_identity(company)
        self.assertFalse(assessment["publishable"])
        self.assertEqual(assessment["status"], "ambiguous")
        self.assertEqual(assessment["automated_identity_result"], "conflicting_identifier")

    # Rule 8: Blocked pages are never crawled in violation of robots.txt
    def test_8_blocked_pages_never_crawled_in_violation_of_robots_txt(self):
        with patch("norway_company_agent.website.assert_public_url"), patch("norway_company_agent.website._robots_allowed", return_value=False):
            rec, ops = fetch_website("https://example.com/private")
            self.assertEqual(rec["status"], "blocked")
            self.assertIn("robots.txt", rec.get("note", ""))

        profile = {
            "organisation_number": "999000111",
            "name": "Private Enterprise AS",
            "evidence": {
                "website": {
                    "status": "blocked",
                    "source_url": "https://example.com/private",
                    "value": {},
                }
            },
        }
        claims, evidence_list = synthesize_claims_and_evidence(profile)
        website_claim = next(c for c in claims if c["field"] == "official_website")
        self.assertEqual(website_claim["availability"], "blocked")
        self.assertIsNone(website_claim["value"])

    # Rule 9: Score thresholds and decision rules cannot contradict each other
    def test_9_score_thresholds_and_decision_rules_cannot_contradict(self):
        test_cases = [
            # Exact org match
            {"org": "990918546", "name": "Test AS", "text": "Test AS 990918546", "title": "Test AS", "postcode": None},
            # Address match
            {"org": "990918546", "name": "Test AS", "text": "Test AS, 0277 Oslo", "title": "Test AS", "postcode": "0277"},
            # Title only (no address or org) -> ambiguous
            {"org": "990918546", "name": "Test AS", "text": "Test AS general text", "title": "Test AS", "postcode": "0277"},
            # Conflicting org
            {"org": "990918546", "name": "Test AS", "text": "Test AS 999111222", "title": "Test AS", "postcode": None},
            # Parked
            {"org": "990918546", "name": "Test AS", "text": "domain is for sale", "title": "Test AS", "postcode": None},
        ]
        for tc in test_cases:
            p = {
                "organisation_number": tc["org"],
                "name": tc["name"],
                "postcode": tc["postcode"],
                "evidence": {
                    "website": {
                        "status": "available",
                        "value": {
                            "title": tc["title"],
                            "main_text_excerpt": tc["text"],
                        },
                    }
                },
            }
            res = assess_website_identity(p)
            if res["publishable"]:
                self.assertEqual(res["status"], "exact")
                self.assertGreaterEqual(res["score"], 0.95)
            else:
                self.assertEqual(res["status"], "ambiguous")
                self.assertLess(res["score"], 0.95)

    # Rule 10: Human review remains not_reviewed unless explicitly supplied by a person
    def test_10_human_review_remains_not_reviewed_unless_explicitly_supplied(self):
        profiles = [
            # Exact match
            {"organisation_number": "990918546", "name": "Scatec ASA", "evidence": {"website": {"status": "available", "value": {"title": "Scatec", "identity_text_excerpt": "990918546"}}}},
            # Combined match
            {"organisation_number": "912345678", "name": "Norsk Fiske AS", "postcode": "6002", "evidence": {"website": {"status": "available", "value": {"title": "Norsk Fiske AS", "main_text_excerpt": "6002"}}}},
            # Ambiguous
            {"organisation_number": "911222333", "name": "Unknown AS", "evidence": {"website": {"status": "available", "value": {"title": "Different"}}}},
            # Parked
            {"organisation_number": "955666777", "name": "Parked AS", "evidence": {"website": {"status": "available", "value": {"title": "HugeDomains is parked"}}}},
        ]
        for prof in profiles:
            assessment = assess_website_identity(prof)
            self.assertEqual(assessment["human_review_status"], "not_reviewed")

    # Additional edge cases: Parked domains and social gating
    def test_parked_domain_markers_receive_lowest_score(self):
        profile = {
            "organisation_number": "955666777",
            "name": "Acme Ventures AS",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.acmeventures.com/",
                        "title": "Acmeventures.com is for sale | HugeDomains",
                        "description": "Domain for sale",
                        "main_text_excerpt": "This domain is parked at HugeDomains.",
                    },
                }
            },
        }
        assessment = assess_website_identity(profile)
        self.assertEqual(assessment["score"], 0.1)
        self.assertFalse(assessment["publishable"])
        self.assertEqual(assessment["status"], "ambiguous")
        self.assertEqual(assessment["automated_identity_result"], "parked_or_placeholder")

    def test_apply_website_identity_gate_quarantines_parent_social_links(self):
        profile = {
            "organisation_number": "966777888",
            "name": "Aon Assessment Norge AS",
            "postcode": "0277",
            "evidence": {},
        }
        website = {
            "status": "available",
            "value": {
                "final_url": "https://www.aon.com/norway",
                "title": "Aon Assessment Norge AS",
                "main_text_excerpt": "Aon Assessment Norge AS, 0277 Oslo.",
                "social_links": [
                    {"platform": "linkedin", "url": "https://www.linkedin.com/company/aon"},
                    {"platform": "linkedin", "url": "https://www.linkedin.com/company/aon-assessment-norge"},
                ],
            },
        }
        result = apply_website_identity_gate(profile, website)
        self.assertTrue(result["assessment"]["publishable"])
        published_urls = [s["url"] for s in result["website"]["value"]["social_links"]]
        self.assertIn("https://www.linkedin.com/company/aon-assessment-norge", published_urls)
        self.assertNotIn("https://www.linkedin.com/company/aon", published_urls)
        self.assertEqual(result["quarantined_social_links"], 1)


if __name__ == "__main__":
    unittest.main()
