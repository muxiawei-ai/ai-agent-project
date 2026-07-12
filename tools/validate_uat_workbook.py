#!/usr/bin/env python3
"""Regression checks for the governed AI customer-service UAT workbook."""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def cell_text(cell: ET.Element) -> str:
    inline = cell.find("m:is", NS)
    if inline is not None:
        return "".join(node.text or "" for node in inline.findall(".//m:t", NS))
    value = cell.find("m:v", NS)
    return value.text if value is not None and value.text is not None else ""


def sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"].lstrip("/")
        for rel in rels.findall("r:Relationship", REL_NS)
    }
    return {
        sheet.attrib["name"]: targets[sheet.attrib[RID]]
        for sheet in workbook.findall("m:sheets/m:sheet", NS)
    }


def table_path_for_sheet(archive: zipfile.ZipFile, sheet_path: str) -> str:
    rel_path = sheet_path.replace("worksheets/", "worksheets/_rels/") + ".rels"
    rels = ET.fromstring(archive.read(rel_path))
    for rel in rels.findall("r:Relationship", REL_NS):
        if rel.attrib["Type"].endswith("/table"):
            target = rel.attrib["Target"]
            if target.startswith("/"):
                return target.lstrip("/")
            return "xl/" + target.split("../", 1)[-1]
    raise AssertionError(f"No table relationship found for {sheet_path}")


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    workbook_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else repo / "02-templates" / "AI客服-UAT-执行模板.xlsx"
    )
    failures: list[str] = []

    with zipfile.ZipFile(workbook_path) as archive:
        paths = sheet_paths(archive)

        run_table_path = table_path_for_sheet(archive, paths["05_Run_Results"])
        run_table = ET.fromstring(archive.read(run_table_path))
        run_ref = run_table.attrib.get("ref", "")
        run_end_match = re.search(r":?[A-Z]+(\d+)$", run_ref)
        run_end_row = int(run_end_match.group(1)) if run_end_match else 0

        scoring = ET.fromstring(archive.read(paths["06_Scoring"]))
        exact_controls = {
            "01_KB_Catalog": {"O2"},
            "06_Scoring": {"M2", "N2", "O2", "Z2"},
        }
        for sheet_name, references in exact_controls.items():
            root = ET.fromstring(archive.read(paths[sheet_name]))
            formulas = {
                cell.attrib["r"]: (cell.find("m:f", NS).text or "")
                for cell in root.findall(".//m:c[m:f]", NS)
            }
            for reference in references:
                if "EXACT(" not in formulas.get(reference, "").upper():
                    fail(
                        f"{sheet_name}!{reference} no longer enforces case-sensitive exact matching",
                        failures,
                    )

        metadata_error_guards = {"V2", "W2", "X2", "Y2"}
        scoring_formulas = {
            cell.attrib["r"]: (cell.find("m:f", NS).text or "")
            for cell in scoring.findall(".//m:c[m:f]", NS)
        }
        for reference in metadata_error_guards:
            if "IFERROR(" not in scoring_formulas.get(reference, "").upper():
                fail(
                    f"06_Scoring!{reference} does not safely project optional execution metadata",
                    failures,
                )
        formula_rows = []
        for cell in scoring.findall(".//m:c[m:f]", NS):
            match = re.search(r"(\d+)$", cell.attrib["r"])
            if match:
                formula_rows.append(int(match.group(1)))
        if not formula_rows or max(formula_rows) < run_end_row:
            fail(
                "06_Scoring formulas do not cover the prepared RunResults table",
                failures,
            )

        scoring_table_path = table_path_for_sheet(archive, paths["06_Scoring"])
        scoring_table = ET.fromstring(archive.read(scoring_table_path))
        table_ref = scoring_table.attrib.get("ref", "")
        end_match = re.search(r":?[A-Z]+(\d+)$", table_ref)
        if not end_match or int(end_match.group(1)) < run_end_row:
            fail(
                f"ScoringTable ends at {table_ref or 'unknown'}, before {run_ref or 'RunResults'}",
                failures,
            )

        dashboard = ET.fromstring(archive.read(paths["07_Dashboard"]))
        rate_formulas = []
        for cell in dashboard.findall(".//m:c[m:f]", NS):
            row = int(re.search(r"(\d+)$", cell.attrib["r"]).group(1))
            formula = cell.find("m:f", NS).text or ""
            if 6 <= row <= 14 and "5000" in formula:
                rate_formulas.append((cell.attrib["r"], formula))
        missing_blocked_filter = [
            ref
            for ref, formula in rate_formulas
            if '"<>BLOCKED"' not in formula.replace(" ", "").upper()
        ]
        if not rate_formulas or missing_blocked_filter:
            fail(
                "Dashboard rate denominators do not consistently exclude BLOCKED rows"
                + (f" ({', '.join(missing_blocked_filter)})" if missing_blocked_filter else ""),
                failures,
            )

        selfcheck = ET.fromstring(archive.read(paths["99_Selfcheck"]))
        selfcheck_text = "\n".join(
            cell_text(cell) for cell in selfcheck.findall(".//m:c", NS)
        )
        for required in (
            "CASE-DEMO-006",
            "NOT_APPROVED",
            "CASE-DEMO-007",
            "VERSION_MISMATCH",
        ):
            if required not in selfcheck_text:
                fail(
                    f"99_Selfcheck lacks an explicit negative-path assertion for {required}",
                    failures,
                )

        lookups = ET.fromstring(archive.read(paths["08_Lookups"]))
        failure_types = {
            cell_text(cell).strip()
            for cell in lookups.findall(".//m:c", NS)
            if cell.attrib.get("r", "").startswith("G")
        }
        if "INCONSISTENT" in failure_types:
            fail(
                "08_Lookups.failure_type still contains INCONSISTENT; use Consistency_Flag instead",
                failures,
            )

    rules_path = repo / "03-rules" / "数据字段与枚举.md"
    rules_text = rules_path.read_text(encoding="utf-8")
    delimiter_rule = re.search(
        r"(?:禁止|不得|不允许)[^\n]{0,100}\|\|\|[^\n]{0,100}(?:成员|答案|转义)",
        rules_text,
    )
    if not delimiter_rule:
        fail(
            "Data-field rules do not explicitly prohibit an unescaped ||| inside an acceptable-answer member",
            failures,
        )

    if not (repo / "tools" / "prepare_uat_workbook.py").is_file():
        fail("Deterministic workbook capacity preparer is missing", failures)

    if failures:
        print(f"FAIL: {len(failures)} regression check(s) failed")
        for item in failures:
            print(f"- {item}")
        return 1

    print("PASS: governed UAT workbook regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
