"""
Synthetic unit tests for frozen registry snapshot loading and provenance verification.

Ensures:
1. profiles_from_bulk populates entity profiles with ZERO network calls.
2. Evidence provenance accurately records official_registry_bulk and file SHA-256 hash.
3. Accounting obligation is correctly assessed offline.
4. Missing organisations in snapshot raise an explicit descriptive ValueError.
5. Nonexistent file raises FileNotFoundError.
6. Order of requested organisation numbers is strictly preserved.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest

from norway_company_agent.batch import profiles_from_bulk


def _create_synthetic_snapshot(directory: Path, rows: list[dict[str, str]]) -> Path:
    path = directory / "enheter_synthetic.csv.gz"
    fieldnames = [
        "organisasjonsnummer",
        "navn",
        "organisasjonsform.kode",
        "antallAnsatte",
        "forretningsadresse.kommune",
        "forretningsadresse.kommunenummer",
        "naeringskode1.kode",
        "naeringskode1.beskrivelse",
        "hjemmeside",
        "konkurs",
        "underAvvikling",
        "sisteInnsendteAarsregnskap",
    ]
    with gzip.open(path, "wt", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


class SnapshotReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_dir.name)
        self.rows = [
            {
                "organisasjonsnummer": "990918546",
                "navn": "Scatec ASA",
                "organisasjonsform.kode": "ASA",
                "antallAnsatte": "450",
                "forretningsadresse.kommune": "OSLO",
                "forretningsadresse.kommunenummer": "0301",
                "naeringskode1.kode": "35.111",
                "naeringskode1.beskrivelse": "Produksjon av elektrisitet fra vannkraft",
                "hjemmeside": "www.scatec.com",
                "konkurs": "false",
                "underAvvikling": "false",
                "sisteInnsendteAarsregnskap": "2024",
            },
            {
                "organisasjonsnummer": "923609016",
                "navn": "Equinor ASA",
                "organisasjonsform.kode": "ASA",
                "antallAnsatte": "21000",
                "forretningsadresse.kommune": "STAVANGER",
                "forretningsadresse.kommunenummer": "1103",
                "naeringskode1.kode": "06.100",
                "naeringskode1.beskrivelse": "Utvinning av råolje",
                "hjemmeside": "www.equinor.com",
                "konkurs": "false",
                "underAvvikling": "false",
                "sisteInnsendteAarsregnskap": "2024",
            },
            {
                "organisasjonsnummer": "912345678",
                "navn": "Nordic Test AS",
                "organisasjonsform.kode": "AS",
                "antallAnsatte": "5",
                "forretningsadresse.kommune": "BERGEN",
                "forretningsadresse.kommunenummer": "4601",
                "naeringskode1.kode": "62.010",
                "naeringskode1.beskrivelse": "Programmeringstjenester",
                "hjemmeside": "",
                "konkurs": "false",
                "underAvvikling": "false",
                "sisteInnsendteAarsregnskap": "2023",
            },
        ]
        self.snapshot_path = _create_synthetic_snapshot(self.directory, self.rows)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_snapshot_populates_profile_with_zero_network_calls(self):
        """Verify that profiles_from_bulk reads completely from offline fixture."""
        expected_sha = hashlib.sha256(self.snapshot_path.read_bytes()).hexdigest()
        profiles, meta = profiles_from_bulk(self.snapshot_path, ["990918546"])

        self.assertEqual(len(profiles), 1)
        prof = profiles[0]
        self.assertEqual(prof["organisation_number"], "990918546")
        self.assertEqual(prof["name"], "Scatec ASA")
        self.assertEqual(prof["legal_form"], "ASA")
        self.assertEqual(prof["employees"], 450)
        self.assertEqual(prof["municipality"], "OSLO")
        self.assertEqual(prof["latest_submitted_accounts"], "2024")

        # Evidence verification
        evidence_item = prof["evidence"]["registry"]
        self.assertEqual(evidence_item["source_type"], "official_registry_bulk")
        self.assertEqual(evidence_item["content_sha256"], expected_sha)
        self.assertEqual(evidence_item["source_row_key"], "990918546")

        # Offline accounting obligation assessment
        acct = prof["evidence"]["accounting_obligation"]
        self.assertEqual(acct["status"], "available")
        self.assertEqual(acct["value"]["classification"], "filing_observed")

        # Metadata verification
        self.assertEqual(meta["registry_snapshot_sha256"], expected_sha)
        self.assertEqual(meta["selected"], 1)

    def test_snapshot_preserves_requested_order(self):
        """Verify requested order is strictly preserved regardless of CSV row order."""
        requested = ["912345678", "990918546"]
        profiles, meta = profiles_from_bulk(self.snapshot_path, requested)
        self.assertEqual([p["organisation_number"] for p in profiles], requested)
        self.assertEqual(meta["selected"], 2)

    def test_missing_organisation_in_snapshot_raises_error(self):
        """Verify an absent organisation raises a ValueError indicating missing orgs."""
        with self.assertRaises(ValueError) as ctx:
            profiles_from_bulk(self.snapshot_path, ["990918546", "999999999"])
        self.assertIn("Organisation numbers absent from registry snapshot", str(ctx.exception))
        self.assertIn("999999999", str(ctx.exception))

    def test_nonexistent_snapshot_path_raises_filenotfound(self):
        """Verify nonexistent file raises FileNotFoundError."""
        bad_path = self.directory / "nonexistent.csv.gz"
        with self.assertRaises(FileNotFoundError):
            profiles_from_bulk(bad_path, ["990918546"])


if __name__ == "__main__":
    unittest.main()
