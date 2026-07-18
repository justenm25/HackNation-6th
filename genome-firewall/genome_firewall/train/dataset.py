from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix, load_npz

from ..exceptions import InputValidationError
from ..featurize.schema import FeatureSchema
from ..grouping.minhash import compute_mash_groups
from ..labels.policy import normalize_label


@dataclass
class PreparedDataset:
    X: csr_matrix
    sample_ids: list[str]
    split_by_sample: dict[str, str]
    group_by_sample: dict[str, str]
    labels_by_drug: dict[str, np.ndarray]
    feature_schema: FeatureSchema


def load_prepared_dataset(path: str | Path, *, drug_ids: list[str], grouping_config: dict | None = None,
                          label_config: dict | None = None) -> PreparedDataset:
    root = Path(path)
    schema = FeatureSchema.load(root / "feature_schema.json")
    X = load_npz(root / "X_features.npz").tocsr()
    with (root / "samples.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    sample_ids = [row.get("sample_id", "") for row in rows]
    if not sample_ids or any(not sample for sample in sample_ids) or len(sample_ids) != len(set(sample_ids)):
        raise InputValidationError("samples.csv requires unique, non-empty sample_id values")
    if X.shape != (len(rows), len(schema.columns)):
        raise InputValidationError("X_features.npz shape does not match samples.csv and feature schema")
    valid_splits = {"train", "calibration", "hidden_test"}
    split_by_sample = {row["sample_id"]: row.get("split", "") for row in rows}
    if not set(split_by_sample.values()) <= valid_splits:
        raise InputValidationError(f"Splits must be in {sorted(valid_splits)}")
    supplied_groups = all(row.get("genetic_group_id") for row in rows)
    if supplied_groups:
        group_by_sample = {row["sample_id"]: row["genetic_group_id"] for row in rows}
    else:
        if not all(row.get("fasta_path") for row in rows):
            raise InputValidationError("Missing genetic groups requires fasta_path for every sample")
        settings = grouping_config or {}
        group_by_sample, _ = compute_mash_groups(
            {row["sample_id"]: root / row["fasta_path"] for row in rows},
            distance_threshold=float(settings.get("distance_threshold", 0.001)),
            kmer_size=int(settings.get("mash_kmer_size", 21)),
            sketch_size=int(settings.get("mash_sketch_size", 10000)),
            executable=settings.get("executable", "mash"),
        )
    policy = label_config or {}
    labels_by_drug = {}
    for drug in drug_ids:
        if drug not in (rows[0] if rows else {}):
            raise InputValidationError(f"samples.csv lacks phenotype column: {drug}")
        values = [normalize_label(row.get(drug), resistant_values=policy.get("resistant_values", ("R",)),
                                  susceptible_values=policy.get("susceptible_values", ("S",)),
                                  intermediate_values=policy.get("intermediate_values", ("I",)),
                                  intermediate_policy=policy.get("intermediate_policy", "exclude")) for row in rows]
        labels_by_drug[drug] = np.array([np.nan if value is None else value for value in values], dtype=float)
    return PreparedDataset(X, sample_ids, split_by_sample, group_by_sample, labels_by_drug, schema)
