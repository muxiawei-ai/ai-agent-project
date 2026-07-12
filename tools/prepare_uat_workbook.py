#!/usr/bin/env python3
"""Prepare the governed UAT workbook for an exact, approved row capacity.

This is a deterministic packaging utility: it copies existing governed formulas,
resizes Excel tables, and requests a full recalculation on open. It does not
generate cases, change answers, or make approval decisions.
"""

from __future__ import annotations

import argparse
import copy
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"m": MAIN_NS, "r": REL_NS}
ET.register_namespace("", MAIN_NS)
ET.register_namespace("r", DOC_REL_NS)


def column_number(label: str) -> int:
    value = 0
    for char in label:
        value = value * 26 + ord(char) - ord("A") + 1
    return value


def cell_column(reference: str) -> str:
    match = re.match(r"([A-Z]+)", reference)
    if not match:
        raise ValueError(f"Invalid cell reference: {reference}")
    return match.group(1)


def translate_seed_formula(formula: str, seed_row: int, target_row: int) -> str:
    pattern = re.compile(rf"(\$?[A-Z]{{1,3}}){seed_row}\b")
    return pattern.sub(lambda match: f"{match.group(1)}{target_row}", formula)


def worksheet_paths(files: dict[str, bytes]) -> dict[str, str]:
    workbook = ET.fromstring(files["xl/workbook.xml"])
    rels = ET.fromstring(files["xl/_rels/workbook.xml.rels"])
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"].lstrip("/")
        for rel in rels.findall("r:Relationship", NS)
    }
    rid_key = f"{{{DOC_REL_NS}}}id"
    return {
        sheet.attrib["name"]: targets[sheet.attrib[rid_key]]
        for sheet in workbook.findall("m:sheets/m:sheet", NS)
    }


def set_dimension(root: ET.Element, last_column: str, last_row: int) -> None:
    dimension = root.find("m:dimension", NS)
    if dimension is None:
        dimension = ET.Element(f"{{{MAIN_NS}}}dimension")
        root.insert(0, dimension)
    dimension.attrib["ref"] = f"A1:{last_column}{last_row}"


def ensure_formula_capacity(
    root: ET.Element,
    *,
    seed_row_number: int,
    last_row: int,
    last_column: str,
) -> None:
    sheet_data = root.find("m:sheetData", NS)
    if sheet_data is None:
        raise ValueError("Worksheet has no sheetData")
    rows = {
        int(row.attrib["r"]): row
        for row in sheet_data.findall("m:row", NS)
        if "r" in row.attrib
    }
    seed_row = rows.get(seed_row_number)
    if seed_row is None:
        raise ValueError(f"Formula seed row {seed_row_number} is missing")
    templates = {
        cell_column(cell.attrib["r"]): cell
        for cell in seed_row.findall("m:c", NS)
        if cell.find("m:f", NS) is not None
    }
    if not templates:
        raise ValueError(f"Formula seed row {seed_row_number} has no formulas")

    for row_number in range(seed_row_number, last_row + 1):
        row = rows.get(row_number)
        if row is None:
            row = ET.Element(f"{{{MAIN_NS}}}row", {"r": str(row_number)})
            sheet_data.append(row)
            rows[row_number] = row
        existing = {
            cell_column(cell.attrib["r"]): cell
            for cell in row.findall("m:c", NS)
        }
        for column, template in templates.items():
            cell = existing.get(column)
            if cell is None:
                cell = copy.deepcopy(template)
                row.append(cell)
            cell.attrib["r"] = f"{column}{row_number}"
            formula = cell.find("m:f", NS)
            if formula is None:
                formula = ET.SubElement(cell, f"{{{MAIN_NS}}}f")
            seed_formula = template.find("m:f", NS).text or ""
            formula.text = translate_seed_formula(
                seed_formula, seed_row_number, row_number
            )
            for value in list(cell.findall("m:v", NS)):
                cell.remove(value)
        row[:] = sorted(
            row,
            key=lambda cell: column_number(cell_column(cell.attrib.get("r", "A1"))),
        )

    sheet_data[:] = sorted(
        sheet_data,
        key=lambda row: int(row.attrib.get("r", "0")),
    )
    set_dimension(root, last_column, last_row)


def resize_tables(files: dict[str, bytes], targets: dict[str, str]) -> None:
    for name, payload in list(files.items()):
        if not name.startswith("xl/tables/") or not name.endswith(".xml"):
            continue
        root = ET.fromstring(payload)
        table_name = root.attrib.get("displayName") or root.attrib.get("name")
        target = targets.get(table_name)
        if target is None:
            continue
        root.attrib["ref"] = target
        auto_filter = root.find("m:autoFilter", NS)
        if auto_filter is not None:
            auto_filter.attrib["ref"] = target
        files[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)


def request_full_recalculation(files: dict[str, bytes]) -> None:
    root = ET.fromstring(files["xl/workbook.xml"])
    calc_pr = root.find("m:calcPr", NS)
    if calc_pr is None:
        calc_pr = ET.SubElement(root, f"{{{MAIN_NS}}}calcPr")
    calc_pr.attrib.update(
        {"calcMode": "auto", "fullCalcOnLoad": "1", "forceFullCalc": "1"}
    )
    files["xl/workbook.xml"] = ET.tostring(
        root, encoding="utf-8", xml_declaration=True
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare UAT workbook formula/table capacity after case count approval."
    )
    parser.add_argument("source", type=Path, help="Source governed .xlsx template")
    parser.add_argument("output", type=Path, help="Prepared .xlsx output path")
    parser.add_argument(
        "--case-rows",
        type=int,
        default=3000,
        help="Number of candidate/frozen/run/scoring data rows (default: 3000)",
    )
    parser.add_argument(
        "--kb-rows",
        type=int,
        default=500,
        help="Number of knowledge-base data rows (default: 500)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 10 <= args.case_rows <= 4999:
        raise SystemExit("--case-rows must be between 10 and 4999")
    if not 2 <= args.kb_rows <= 4999:
        raise SystemExit("--kb-rows must be between 2 and 4999")
    if args.source.suffix.lower() != ".xlsx" or args.output.suffix.lower() != ".xlsx":
        raise SystemExit("source and output must both be .xlsx files")

    with zipfile.ZipFile(args.source) as archive:
        infos = archive.infolist()
        files = {info.filename: archive.read(info.filename) for info in infos}

    paths = worksheet_paths(files)
    case_last_row = args.case_rows + 1
    kb_last_row = args.kb_rows + 1

    formula_specs = (
        ("01_KB_Catalog", kb_last_row, "T"),
        ("04_Frozen_Cases", case_last_row, "N"),
        ("06_Scoring", case_last_row, "AA"),
    )
    for sheet_name, last_row, last_column in formula_specs:
        root = ET.fromstring(files[paths[sheet_name]])
        ensure_formula_capacity(
            root,
            seed_row_number=2,
            last_row=last_row,
            last_column=last_column,
        )
        files[paths[sheet_name]] = ET.tostring(
            root, encoding="utf-8", xml_declaration=True
        )

    for sheet_name, last_column in (
        ("03_Candidate_Cases", "W"),
        ("03b_Review_Results", "J"),
        ("05_Run_Results", "J"),
    ):
        root = ET.fromstring(files[paths[sheet_name]])
        set_dimension(root, last_column, case_last_row)
        files[paths[sheet_name]] = ET.tostring(
            root, encoding="utf-8", xml_declaration=True
        )

    resize_tables(
        files,
        {
            "KBCatalogTable": f"A1:T{kb_last_row}",
            "CandidateCasesTable": f"A1:W{case_last_row}",
            "ReviewResultsTable": f"A1:J{case_last_row}",
            "FrozenCasesTable": f"A1:N{case_last_row}",
            "RunResultsTable": f"A1:J{case_last_row}",
            "ScoringTable": f"A1:AA{case_last_row}",
        },
    )
    request_full_recalculation(files)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=args.output.parent, suffix=".xlsx", delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        info_by_name = {info.filename: info for info in infos}
        with zipfile.ZipFile(temporary, "w") as archive:
            for name, payload in files.items():
                archive.writestr(info_by_name[name], payload)
        temporary.replace(args.output)
    finally:
        temporary.unlink(missing_ok=True)

    print(
        f"Prepared {args.output} for {args.case_rows} case rows and "
        f"{args.kb_rows} KB rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
