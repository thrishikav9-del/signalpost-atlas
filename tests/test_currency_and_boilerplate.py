import unittest
from norway_company_agent.canonical_contract import (
    is_boilerplate_description,
    synthesize_claims_and_evidence,
)
from norway_company_agent.research import answer_profile


class TestFinancialCurrencyAndBoilerplate(unittest.TestCase):
    def test_nok_financial_filing_integrity(self):
        """Valid NOK statutory filings must publish values as available with currency NOK."""
        profile = {
            "organisation_number": "123456789",
            "name": "Norsk Bedrift AS",
            "legal_form": "AS",
            "municipality": "OSLO",
            "evidence": {
                "financials": {
                    "status": "available",
                    "source_url": "https://data.brreg.no/regnskapsregisteret/regnskap/123456789",
                    "value": {
                        "records": [
                            {
                                "record_id": 1,
                                "currency": "NOK",
                                "period": {"fraDato": "2023-01-01", "tilDato": "2023-12-31"},
                                "revenue": 50000000.0,
                                "operating_result": 5000000.0,
                                "annual_result": 4000000.0,
                                "assets": 30000000.0,
                                "debt": 10000000.0,
                                "equity": 20000000.0,
                            }
                        ]
                    },
                }
            },
        }
        claims, evidence = synthesize_claims_and_evidence(profile)
        fin_claims = {c["field"]: c for c in claims if "_nok" in c["field"]}
        self.assertEqual(len(fin_claims), 6)
        
        rev = fin_claims["annual_revenue_nok"]
        self.assertEqual(rev["availability"], "available")
        self.assertEqual(rev["value"], 50000000.0)
        self.assertEqual(rev["currency"], "NOK")
        self.assertEqual(rev["reporting_period"]["tilDato"], "2023-12-31")

    def test_usd_filing_never_stored_in_nok_field(self):
        """USD statutory filings (e.g. Equinor, Aker BP) must never be stored in *_nok fields."""
        profile = {
            "organisation_number": "923609016",
            "name": "EQUINOR ASA",
            "legal_form": "ASA",
            "municipality": "STAVANGER",
            "evidence": {
                "financials": {
                    "status": "available",
                    "source_url": "https://data.brreg.no/regnskapsregisteret/regnskap/923609016",
                    "value": {
                        "records": [
                            {
                                "record_id": 5027445,
                                "currency": "USD",
                                "period": {"fraDato": "2023-01-01", "tilDato": "2023-12-31"},
                                "revenue": 107174000000.0,
                                "operating_result": 35770000000.0,
                                "annual_result": 11904000000.0,
                                "assets": 143580000000.0,
                                "debt": 95080000000.0,
                                "equity": 48500000000.0,
                            }
                        ]
                    },
                }
            },
        }
        claims, evidence = synthesize_claims_and_evidence(profile)
        fin_claims = {c["field"]: c for c in claims if "_nok" in c["field"]}
        self.assertEqual(len(fin_claims), 6)
        
        for field_name, claim in fin_claims.items():
            self.assertEqual(claim["availability"], "not_available", f"{field_name} must be not_available for USD filing")
            self.assertIsNone(claim["value"], f"{field_name} must be None (never store USD nominal value in _nok field)")
            self.assertEqual(claim.get("reported_currency"), "USD")
            self.assertIsNotNone(claim.get("reporting_period"))

    def test_eur_filing_never_stored_in_nok_field(self):
        """EUR statutory filings (e.g. Kitron, BEWI) must never be stored in *_nok fields."""
        profile = {
            "organisation_number": "976605713",
            "name": "KITRON ASA",
            "legal_form": "ASA",
            "municipality": "ASKER",
            "evidence": {
                "financials": {
                    "status": "available",
                    "source_url": "https://data.brreg.no/regnskapsregisteret/regnskap/976605713",
                    "value": {
                        "records": [
                            {
                                "record_id": 999,
                                "currency": "EUR",
                                "period": {"fraDato": "2023-01-01", "tilDato": "2023-12-31"},
                                "revenue": 775000000.0,
                                "operating_result": 60000000.0,
                            }
                        ]
                    },
                }
            },
        }
        claims, evidence = synthesize_claims_and_evidence(profile)
        fin_claims = {c["field"]: c for c in claims if "_nok" in c["field"]}
        
        rev = fin_claims["annual_revenue_nok"]
        self.assertEqual(rev["availability"], "not_available")
        self.assertIsNone(rev["value"])
        self.assertEqual(rev.get("reported_currency"), "EUR")

    def test_missing_or_empty_currency_marks_nok_field_unavailable(self):
        """Missing currency information must not assume NOK; must mark *_nok field as not_available."""
        profile = {
            "organisation_number": "112233445",
            "name": "Ukjent Valuta AS",
            "evidence": {
                "financials": {
                    "status": "available",
                    "source_url": "https://data.brreg.no/regnskapsregisteret/regnskap/112233445",
                    "value": {
                        "records": [
                            {
                                "record_id": 2,
                                "currency": None,
                                "period": {"fraDato": "2023-01-01", "tilDato": "2023-12-31"},
                                "revenue": 1000000.0,
                            }
                        ]
                    },
                }
            },
        }
        claims, evidence = synthesize_claims_and_evidence(profile)
        rev = next(c for c in claims if c["field"] == "annual_revenue_nok")
        self.assertEqual(rev["availability"], "not_available")
        self.assertIsNone(rev["value"])

    def test_boilerplate_description_detection(self):
        """CMS and WordPress sample/template strings must be identified as boilerplate."""
        boilerplates = [
            "This is an example page. It's different from a blog post because it will stay in one place and will show up in your site navigation (in most themes). Most people start with an About page that introduces them to potential site visitors. It might say something like this: Hi there! I'm a bike messenger by day, aspiring actor by night, and this is my website.",
            "Just another WordPress site",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            "Default Description for this site",
            "Example Domain. This domain is for use in illustrative examples.",
            "Site description goes here",
            "Under Construction - coming soon",
            "My WordPress Blog",
            "Welcome to WordPress. This is your first post. Edit or delete it, then start writing!",
        ]
        for text in boilerplates:
            self.assertTrue(is_boilerplate_description(text), f"Should detect boilerplate: {text!r}")

        legitimate_descriptions = [
            "Equinor is an international energy company committed to creating long-term value in a low-carbon future.",
            "AF Gruppen | Vi rydder fra fortiden og bygger for fremtiden",
            "Ekte italiensk pizza take-away - MASSIMO PIZZA",
            "A leading Electronics Manufacturing Services company.",
            "Protecting people and goods for a better everyday",
            "Borregaard - The Sustainable Biorefinery",
        ]
        for text in legitimate_descriptions:
            self.assertFalse(is_boilerplate_description(text), f"Should NOT detect boilerplate: {text!r}")

    def test_bewi_asa_boilerplate_description_regression(self):
        """BEWI ASA WordPress template description must be rejected in favor of legitimate H1 slogan."""
        profile = {
            "organisation_number": "925437948",
            "name": "BEWI ASA",
            "legal_form": "ASA",
            "municipality": "FRØYA",
            "evidence": {
                "website": {
                    "status": "available",
                    "source_url": "https://bewi.com/?lang=no",
                    "value": {
                        "title": "Hjem | BEWI",
                        "h1": "Protecting people and goods for a better everyday",
                        "description": "This is an example page. It's different from a blog post because it will stay in one place and will show up in your site navigation (in most themes). Most people start with an About page that introduces them to potential site visitors. It might say something like this: Hi there! I'm a bike messenger — Continued",
                        "identity_assessment": {
                            "publishable": True,
                            "score": 0.95,
                            "selected_tier": "Tier C",
                        },
                    },
                }
            },
        }
        claims, evidence = synthesize_claims_and_evidence(profile)
        desc_claim = next((c for c in claims if c["field"] == "company_description"), None)
        self.assertIsNotNone(desc_claim)
        self.assertEqual(desc_claim["value"], "Protecting people and goods for a better everyday")
        self.assertNotIn("bike messenger", desc_claim["value"])
        self.assertNotIn("example page", desc_claim["value"])

    def test_research_answer_profile_rejects_boilerplate(self):
        """answer_profile should not present boilerplate website descriptions as facts."""
        row = {
            "organisation_number": "925437948",
            "name": "BEWI ASA",
            "evidence": {
                "website": {
                    "status": "available",
                    "source_url": "https://bewi.com/",
                    "value": {
                        "description": "Just another WordPress site",
                        "identity_assessment": {"publishable": True},
                    },
                }
            },
        }
        ans = answer_profile(row, "What does this company do?")
        desc_facts = [f for f in ans["facts"] if f["claim"] == "Website description"]
        self.assertEqual(len(desc_facts), 0)


if __name__ == "__main__":
    unittest.main()
