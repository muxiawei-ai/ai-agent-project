#!/usr/bin/env python3
"""Contract test for the deterministic UAT workbook capacity preparer."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


class PrepareWorkbookTest(unittest.TestCase):
    def test_preparer_expands_formula_and_table_capacity(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        source = repo / "02-templates" / "AI客服-UAT-执行模板.xlsx"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "prepared.xlsx"
            subprocess.run(
                [
                    "python3",
                    str(repo / "tools" / "prepare_uat_workbook.py"),
                    str(source),
                    str(output),
                    "--case-rows",
                    "25",
                    "--kb-rows",
                    "20",
                ],
                check=True,
            )
            with zipfile.ZipFile(output) as archive:
                scoring = ET.fromstring(archive.read("xl/worksheets/sheet8.xml"))
                formulas = {
                    cell.attrib["r"]: cell.find("m:f", NS).text or ""
                    for cell in scoring.findall(".//m:c[m:f]", NS)
                }
                self.assertIn("AA26", formulas)
                self.assertIn("$B26", formulas["AA26"])

                frozen = ET.fromstring(archive.read("xl/worksheets/sheet6.xml"))
                frozen_formulas = {
                    cell.attrib["r"]: cell.find("m:f", NS).text or ""
                    for cell in frozen.findall(".//m:c[m:f]", NS)
                }
                self.assertIn("N26", frozen_formulas)
                self.assertIn("$A26", frozen_formulas["N26"])

                kb = ET.fromstring(archive.read("xl/worksheets/sheet2.xml"))
                kb_formulas = {
                    cell.attrib["r"]: cell.find("m:f", NS).text or ""
                    for cell in kb.findall(".//m:c[m:f]", NS)
                }
                self.assertIn("O21", kb_formulas)
                self.assertIn("$A21", kb_formulas["O21"])

                refs = {
                    name: ET.fromstring(archive.read(name)).attrib["ref"]
                    for name in (
                        "xl/tables/table2.xml",
                        "xl/tables/table4.xml",
                        "xl/tables/table5.xml",
                        "xl/tables/table6.xml",
                        "xl/tables/table7.xml",
                        "xl/tables/table8.xml",
                    )
                }
                self.assertEqual(refs["xl/tables/table2.xml"], "A1:T21")
                self.assertEqual(refs["xl/tables/table4.xml"], "A1:W26")
                self.assertEqual(refs["xl/tables/table5.xml"], "A1:J26")
                self.assertEqual(refs["xl/tables/table6.xml"], "A1:N26")
                self.assertEqual(refs["xl/tables/table7.xml"], "A1:J26")
                self.assertEqual(refs["xl/tables/table8.xml"], "A1:AA26")


if __name__ == "__main__":
    unittest.main()
