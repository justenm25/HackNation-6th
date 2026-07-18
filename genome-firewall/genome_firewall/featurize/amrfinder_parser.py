from __future__ import annotations

import csv
import re
from pathlib import Path

from ..exceptions import InputValidationError
from ..types import NormalizedFinding


GENE_COLUMNS = ("Gene symbol", "Gene", "Element symbol")
MUTATION_COLUMNS = ("Sequence name", "Mutation", "Element symbol")


def _first(row: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        if row.get(name, "").strip():
            return row[name].strip()
    return ""


def _normalize_token(value: str) -> str:
    value = value.strip().replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_.+:-]", "", value)


def _split_mutation(symbol: str, mutation_value: str) -> tuple[str, str] | None:
    value = mutation_value.strip() or symbol.strip()
    match = re.match(r"^([A-Za-z0-9_.-]+)[_: ]+([A-Za-z*]+\d+[A-Za-z*]+)$", value)
    if match:
        return match.group(1), match.group(2)
    if mutation_value.strip() and symbol.strip():
        return symbol.strip(), mutation_value.strip()
    return None


def normalize_row(row: dict[str, str]) -> NormalizedFinding | None:
    symbol = _first(row, GENE_COLUMNS)
    method = row.get("Method", "").strip()
    mutation_value = _first(row, MUTATION_COLUMNS[1:2])
    mutation = _split_mutation(symbol, mutation_value) if ("POINT" in method.upper() or mutation_value) else None
    if mutation:
        gene, change = map(_normalize_token, mutation)
        if not gene or not change:
            return None
        return NormalizedFinding(
            feature_id=f"mutation::{gene}::{change}", kind="point_mutation",
            gene_symbol=gene, mutation=change,
            sequence_name=row.get("Contig id") or row.get("Sequence name"), method=method or None,
            element_subtype=row.get("Element subtype") or row.get("Subtype") or None, raw=dict(row),
        )
    gene = _normalize_token(symbol)
    if not gene or gene in {"NA", "-"}:
        return None
    return NormalizedFinding(
        feature_id=f"gene::{gene}", kind="gene", gene_symbol=gene,
        sequence_name=row.get("Contig id") or row.get("Sequence name"), method=method or None,
        element_subtype=row.get("Element subtype") or row.get("Subtype") or None, raw=dict(row),
    )


def parse_amrfinder_tsv(path: str | Path) -> list[NormalizedFinding]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise InputValidationError("AMRFinder TSV has no header")
        if not any(column in reader.fieldnames for column in GENE_COLUMNS):
            raise InputValidationError(f"AMRFinder TSV lacks a gene column; got {reader.fieldnames}")
        findings = [finding for row in reader if (finding := normalize_row(row))]
    return findings
