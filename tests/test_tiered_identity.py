"""
Unit tests for multi-tier website identity verification policy (tiered_website_identity_v1).
Verifies acceptance and rejection criteria across Tiers A, B, C, and safety boundaries:
- Tier A1: Homepage exact 9-digit org number match
- Tier A2: Secondary contact page exact 9-digit org number match with matching name
- Tier B: Legal name tokens + registered postcode / street address
- Tier C1: Registry-declared link + distinctive legal name + municipality
- Tier C2: Discovered domain with distinctive SLD + legal name + municipality
- Rejection: Conflicting 9-digit organisation number
- Rejection: Parked and placeholder domains
- Rejection: Sports club mismatch
- Rejection: Parent/subsidiary mismatch where name doesn't match
- Rejection: Directory and social media domains
- Separation: human_review_status remains "not_reviewed" across all automated outcomes
- Metadata: identity_evidence schema completeness
"""

from __future__ import annotations

import unittest

from norway_company_agent.identity import assess_website_identity


class TieredWebsiteIdentityTests(unittest.TestCase):
    policy = "tiered_website_identity_v1"

    # Tier A1: Exact identifier on homepage
    def test_tier_a1_homepage_exact_org_number_accepted(self):
        company = {
            "organisation_number": "990918546",
            "name": "Scatec ASA",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.scatec.com/en/",
                        "title": "Scatec - Renewable Energy",
                        "identity_text_excerpt": "Scatec ASA, Org. nr: 990 918 546",
                        "main_text_excerpt": "Leading solar and renewable energy solutions provider.",
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertTrue(res["publishable"])
        self.assertEqual(res["status"], "exact")
        self.assertEqual(res["score"], 1.0)
        self.assertEqual(res["selected_tier"], "Tier A")
        self.assertEqual(res["automated_identity_result"], "tier_a_exact_org")
        self.assertEqual(res["condition_passed"], "A_exact_org_number")
        self.assertEqual(res["identity_evidence"]["matched_identifier"], "990918546")
        self.assertEqual(res["human_review_status"], "not_reviewed")

    # Tier A2: Exact identifier on secondary contact page with matching name
    def test_tier_a2_contact_page_exact_org_number_with_matching_name_accepted(self):
        company = {
            "organisation_number": "980123456",
            "name": "Nordic Tech AS",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.nordictech.no/",
                        "title": "Nordic Tech - Innovative Software",
                        "main_text_excerpt": "We build cloud platforms.",
                        "pages": [
                            {
                                "url": "https://www.nordictech.no/kontakt",
                                "title": "Nordic Tech AS - Kontakt Oss",
                                "identity_text_excerpt": "Nordic Tech AS, Org.nr. 980 123 456",
                                "main_text_excerpt": "Send oss en henvendelse.",
                            }
                        ],
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertTrue(res["publishable"])
        self.assertEqual(res["status"], "exact")
        self.assertEqual(res["score"], 0.98)
        self.assertEqual(res["selected_tier"], "Tier A")
        self.assertEqual(res["automated_identity_result"], "tier_a_exact_org")
        self.assertEqual(res["condition_passed"], "A_exact_org_number")
        self.assertEqual(res["identity_evidence"]["matched_identifier"], "980123456")
        self.assertEqual(res["human_review_status"], "not_reviewed")

    # Tier B: Legal name + registered postcode or street address
    def test_tier_b_legal_name_plus_postcode_or_address_accepted(self):
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
        res = assess_website_identity(company, policy=self.policy)
        self.assertTrue(res["publishable"])
        self.assertEqual(res["status"], "exact")
        self.assertEqual(res["score"], 0.95)
        self.assertEqual(res["selected_tier"], "Tier B")
        self.assertEqual(res["automated_identity_result"], "tier_b_name_and_address")
        self.assertEqual(res["condition_passed"], "B_name_plus_address")
        self.assertEqual(res["identity_evidence"]["matched_postcode"], "6002")
        self.assertEqual(res["human_review_status"], "not_reviewed")

    # Tier C1: Registry-declared website + distinctive legal name + municipality
    def test_tier_c1_registry_declared_website_plus_name_plus_municipality_accepted(self):
        company = {
            "organisation_number": "990263639",
            "name": "Consto AS",
            "website": "http://consto.no",
            "municipality": "Tromsø",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://consto.no/",
                        "title": "Consto | Bygg- og anleggsentreprenør",
                        "description": "Landsdekkende entreprenør",
                        "main_text_excerpt": "Consto er en av Norges ledende entreprenører med hovedkontor i Tromsø.",
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertTrue(res["publishable"])
        self.assertEqual(res["status"], "exact")
        self.assertEqual(res["score"], 0.90)
        self.assertEqual(res["selected_tier"], "Tier C")
        self.assertEqual(res["automated_identity_result"], "tier_c_registry_corroborated")
        self.assertEqual(res["condition_passed"], "C1_registry_link_plus_name_and_locality")
        self.assertEqual(res["identity_evidence"]["evidence_source"], "official_registry")
        self.assertEqual(res["identity_evidence"]["candidate_domain"], "consto.no")
        self.assertEqual(res["identity_evidence"]["extracted_matching_evidence"]["matched_municipality"], "Tromsø")
        self.assertEqual(res["human_review_status"], "not_reviewed")

    # Tier C1 with compound name inflection (buskerudmuseene vs buskerudmuseet)
    def test_tier_c1_compound_name_inflection_accepted(self):
        company = {
            "organisation_number": "991599363",
            "name": "Stiftelsen Buskerudmuseene",
            "website": "http://buskerudmuseene.no",
            "municipality": "Ringerike",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://buskerudmuseene.no/",
                        "title": "Buskerudmuseet - 13 museer og kunstsamlinger i Buskerud",
                        "main_text_excerpt": "Velkommen til museene. Administrasjonen har kontor i Ringerike kommune.",
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertTrue(res["publishable"])
        self.assertEqual(res["selected_tier"], "Tier C")
        self.assertEqual(res["automated_identity_result"], "tier_c_registry_corroborated")

    # Tier C2: Discovered domain with distinctive SLD + name + municipality
    def test_tier_c2_discovered_domain_plus_name_plus_municipality_accepted(self):
        company = {
            "organisation_number": "981776968",
            "name": "Skjæreteknikk AS",
            "municipality": "Hå",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://skjaereteknikk.no/",
                        "title": "Skjæreteknikk AS - Presisjonskutting i Rogaland",
                        "description": "Vannskjæring og laserskjæring",
                        "main_text_excerpt": "Vi leverer skjæretjenester til industrien i Hå kommune.",
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertTrue(res["publishable"])
        self.assertEqual(res["status"], "exact")
        self.assertEqual(res["score"], 0.90)
        self.assertEqual(res["selected_tier"], "Tier C")
        self.assertEqual(res["automated_identity_result"], "tier_c_registry_corroborated")
        self.assertEqual(res["condition_passed"], "C2_discovered_domain_plus_name_and_municipality")
        self.assertEqual(res["identity_evidence"]["evidence_source"], "discovered_domain")
        self.assertEqual(res["human_review_status"], "not_reviewed")

    # Rejection: Conflicting organisation number
    def test_rejection_of_conflicting_org_number(self):
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
        res = assess_website_identity(company, policy=self.policy)
        self.assertFalse(res["publishable"])
        self.assertEqual(res["status"], "ambiguous")
        self.assertEqual(res["score"], 0.3)
        self.assertEqual(res["automated_identity_result"], "conflicting_identifier")
        self.assertIn("922222222", res["identity_evidence"]["conflicting_evidence"])
        self.assertEqual(res["human_review_status"], "not_reviewed")

    # Rejection: Parked and placeholder domains
    def test_rejection_of_parked_and_placeholder_domains(self):
        company = {
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
        res = assess_website_identity(company, policy=self.policy)
        self.assertFalse(res["publishable"])
        self.assertEqual(res["status"], "ambiguous")
        self.assertEqual(res["score"], 0.1)
        self.assertEqual(res["automated_identity_result"], "parked_or_placeholder")
        self.assertEqual(res["human_review_status"], "not_reviewed")

    # Rejection: Sports club pointing to operating company site
    def test_rejection_of_sports_clubs(self):
        company = {
            "organisation_number": "977888999",
            "name": "Aker Solutions B.I.L.",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.akersolutions.com/",
                        "title": "Aker Solutions - Energy Transition",
                        "main_text_excerpt": "Engineering products and services for the energy industry.",
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertFalse(res["publishable"])
        self.assertEqual(res["status"], "ambiguous")
        self.assertEqual(res["score"], 0.3)
        self.assertEqual(res["automated_identity_result"], "sports_club_mismatch")
        self.assertEqual(res["human_review_status"], "not_reviewed")

    # Rejection: Parent/subsidiary mismatch where name doesn't match
    def test_rejection_of_parent_subsidiary_mismatch(self):
        subsidiary = {
            "organisation_number": "981234567",
            "name": "Lyse Produksjon AS",
            "postcode": "4001",
            "municipality": "Stavanger",
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
        res = assess_website_identity(subsidiary, policy=self.policy)
        self.assertFalse(res["publishable"])
        self.assertEqual(res["status"], "ambiguous")
        self.assertIn("insufficient_evidence", res["automated_identity_result"])
        self.assertEqual(res["human_review_status"], "not_reviewed")

    # Rejection: Parent contact page listing subsidiary org number without subsidiary name in title
    def test_rejection_of_parent_contact_page_listing_subsidiaries(self):
        company = {
            "organisation_number": "915637353",
            "name": "SKS PRODUKSJON AS",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://sks.no/",
                        "title": "Konsern - SKS - Forside",
                        "main_text_excerpt": "SKS is a power group with multiple subsidiaries.",
                        "pages": [
                            {
                                "title": "Contact",
                                "main_text_excerpt": "SKS Produksjon AS organisation number 915 637 353",
                            }
                        ],
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertFalse(res["publishable"])
        self.assertEqual(res["status"], "ambiguous")
        self.assertEqual(res["human_review_status"], "not_reviewed")

    # Rejection: Directory and social domains
    def test_rejection_of_directory_and_social_domains(self):
        for url in ["https://www.proff.no/selskap/example", "https://www.linkedin.com/company/example"]:
            company = {
                "organisation_number": "999888777",
                "name": "Example Corp AS",
                "evidence": {
                    "website": {
                        "status": "available",
                        "value": {
                            "final_url": url,
                            "title": "Example Corp AS - Bedriftsinformasjon",
                            "main_text_excerpt": "Example Corp AS Org.nr: 999 888 777",
                        },
                    }
                },
            }
            res = assess_website_identity(company, policy=self.policy)
            self.assertFalse(res["publishable"])
            self.assertEqual(res["status"], "ambiguous")

    # Schema completeness: identity_evidence contains all required fields
    def test_identity_evidence_contains_all_required_schema_fields(self):
        company = {
            "organisation_number": "999296432",
            "name": "Entra ASA",
            "website": "https://www.entra.no",
            "municipality": "Oslo",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.entra.no/",
                        "title": "Entra | Kontorlokaler i Oslo",
                        "main_text_excerpt": "Entra er et ledende eiendomsselskap med hovedkontor i Oslo.",
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertTrue(res["publishable"])
        evidence = res["identity_evidence"]
        required_fields = [
            "target_organisation_number",
            "candidate_domain",
            "evidence_source",
            "selected_tier",
            "extracted_matching_evidence",
            "conflicting_evidence",
            "matched_identifier",
            "matched_tokens",
            "matched_address",
            "matched_postcode",
            "url",
            "location",
            "excerpt",
        ]
        for field in required_fields:
            self.assertIn(field, evidence, f"Missing required evidence field: {field}")
        self.assertEqual(evidence["target_organisation_number"], "999296432")
        self.assertEqual(evidence["candidate_domain"], "entra.no")
        self.assertEqual(evidence["selected_tier"], "Tier C")

    # Regression Tests: Address-matching bug fixes & short-token false positives
    def test_aon_norway_short_token_and_unrelated_number_false_match_rejected(self):
        """Exact reproduction of the AON bug: company registered at St. Olavs plass 5,

        page text has 'Australia' ('st' substring) and unrelated digit '5'.
        Must NOT pass Tier B. Must remain ambiguous/unpublishable.
        """
        company = {
            "organisation_number": "966703687",
            "name": "Aon Norway AS",
            "postcode": "0165",
            "address": "St. Olavs plass 5",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.aon.com/nb-no/",
                        "title": "Aon i Norge",
                        "pages": [
                            {
                                "url": "https://www.aon.com/en/about/leadership-and-governance/privacy-policy",
                                "title": "Privacy Policy",
                                "main_text_excerpt": "e. - Asia Pacific Australia China Fiji Hong Kong India Indonesia Japan and 5 years data retention.",
                            }
                        ],
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertFalse(res["publishable"], "Aon Norway privacy policy must not trigger address verification")
        self.assertEqual(res["status"], "ambiguous")
        self.assertIsNone(res["condition_passed"])
        self.assertIsNone(res["identity_evidence"]["matched_address"])
        self.assertIsNone(res["identity_evidence"]["matched_postcode"])

    def test_short_street_fragment_dr_gt_cannot_trigger_address_match(self):
        """Short fragments like 'dr' or 'gt' appearing in unrelated words must not match street addresses."""
        company = {
            "organisation_number": "922333444",
            "name": "Norsk Tannhelse AS",
            "postcode": "5003",
            "address": "Dr. Holms vei 8",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.norsktannhelse.no/",
                        "title": "Norsk Tannhelse AS",
                        "main_text_excerpt": "We welcome children from age 8 to our modern dental clinic.",
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertFalse(res["publishable"], "Word 'children' + number 8 must not match 'Dr. Holms vei 8'")
        self.assertIsNone(res["identity_evidence"]["matched_address"])

    def test_unassociated_house_number_at_distance_rejected(self):
        """Street name in header and house number far away in footer must not match."""
        company = {
            "organisation_number": "933444555",
            "name": "Bergen Handel AS",
            "postcode": "5001",
            "address": "Strandgaten 4",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.bergenhandel.no/",
                        "title": "Bergen Handel AS - Velkommen",
                        "main_text_excerpt": "Vår butikk i Strandgaten tilbyr et bredt utvalg av varer. " + ("x " * 80) + "Side 4 av 10.",
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertFalse(res["publishable"], "House number 4 over 100 chars away from Strandgaten must not match")
        self.assertIsNone(res["identity_evidence"]["matched_address"])

    def test_standalone_copyright_year_cannot_satisfy_postcode(self):
        """A registered postcode like 2024 must not match a copyright notice without address context."""
        company = {
            "organisation_number": "944555666",
            "name": "Byggfornying AS",
            "postcode": "2024",
            "address": "Industriveien 10",
            "municipality": "LILLESTRØM",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.byggfornying.no/",
                        "title": "Byggfornying AS - Hjem",
                        "main_text_excerpt": "Copyright © 2024 Byggfornying AS. All rights reserved.",
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertFalse(res["publishable"], "Copyright 2024 must not trigger postcode verification for 2024")
        self.assertIsNone(res["identity_evidence"]["matched_postcode"])

    def test_valid_street_and_adjacent_house_number_passes(self):
        """A genuine street name with house number in close proximity passes Tier B."""
        company = {
            "organisation_number": "955666777",
            "name": "Oslo Rørlegger AS",
            "address": "Standardveien 1",
            "evidence": {
                "website": {
                    "status": "available",
                    "value": {
                        "final_url": "https://www.osloror.no/",
                        "title": "Oslo Rørlegger AS",
                        "main_text_excerpt": "Besøksadresse: Standardveien 1 i Oslo.",
                    },
                }
            },
        }
        res = assess_website_identity(company, policy=self.policy)
        self.assertTrue(res["publishable"])
        self.assertEqual(res["selected_tier"], "Tier B")
        self.assertEqual(res["identity_evidence"]["matched_address"], "Standardveien 1")


if __name__ == "__main__":
    unittest.main()

