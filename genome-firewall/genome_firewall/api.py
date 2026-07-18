from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from .exceptions import InputValidationError
from .featurize.amrfinder_parser import parse_amrfinder_tsv
from .featurize.amrfinder_runner import run_amrfinder
from .predict.engine import PredictionEngine
from .report.builder import build_report
from .types import NormalizedFinding, PredictionReport


def predict(input_path: str | Path, *, bundle_path: str | Path, input_format: str = "fasta",
            sample_id: str | None = None, species_id: str = "escherichia_coli",
            amrfinder_executable: str = "amrfinder", amrfinder_database_dir: str | None = None,
            marker_free_susceptible_policy: str = "conservative") -> PredictionReport:
    path = Path(input_path)
    if not path.is_file():
        raise InputValidationError(f"Input not found: {path}")
    engine = PredictionEngine(bundle_path)
    fasta_hash = None
    if input_format == "fasta":
        fasta_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix="genome-firewall-") as temp:
            tsv = Path(temp) / "amrfinder.tsv"
            run_amrfinder(path, tsv, executable=amrfinder_executable,
                          database_dir=amrfinder_database_dir)
            findings = parse_amrfinder_tsv(tsv)
    elif input_format == "amrfinder_tsv":
        findings = parse_amrfinder_tsv(path)
    elif input_format == "feature_matrix":
        findings = _load_single_feature_json(path, engine)
    else:
        raise InputValidationError(f"Unknown input_format: {input_format}")
    predictions, unknown = engine.predict_findings(
        findings, species_id=species_id, marker_free_susceptible_policy=marker_free_susceptible_policy)
    return build_report(sample_id=sample_id or path.stem, input_type=input_format, species_id=species_id,
                        predictions=predictions, bundle_id=engine.bundle.name,
                        feature_schema_id=engine.schema.schema_id, unknown_features=unknown,
                        fasta_sha256=fasta_hash)


def _load_single_feature_json(path: Path, engine: PredictionEngine) -> list[NormalizedFinding]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_id") != engine.schema.schema_id:
        raise InputValidationError("Feature matrix schema_id does not match model bundle")
    columns = payload.get("columns")
    engine.schema.validate_columns(columns)
    values = payload.get("values")
    if not isinstance(values, list) or len(values) != len(columns) or any(value not in (0, 1) for value in values):
        raise InputValidationError("Single feature matrix values must be one aligned binary row")
    return [NormalizedFinding(feature_id=name, kind=name.split("::", 1)[0],
                              gene_symbol=name.split("::")[1]) for name, value in zip(columns, values) if value]
