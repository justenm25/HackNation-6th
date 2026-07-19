import json

import numpy as np
from scipy.sparse import csr_matrix

from genome_firewall.featurize.schema import FeatureSchema
from genome_firewall.predict.engine import PredictionEngine
from genome_firewall.train.pipeline import train_bundle
from genome_firewall.types import NormalizedFinding


def test_training_bundle_roundtrip(tmp_path):
    sample_ids = [f"s{i}" for i in range(24)]
    splits = {sample: ("train" if i < 12 else "calibration" if i < 18 else "hidden_test")
              for i, sample in enumerate(sample_ids)}
    groups = {sample: f"group_{i}" for i, sample in enumerate(sample_ids)}
    labels = np.array([i % 2 for i in range(24)], dtype=float)
    X = csr_matrix(np.column_stack([labels, 1 - labels]))
    schema = FeatureSchema.fit([
        [NormalizedFinding("gene::res", "gene", "res")],
        [NormalizedFinding("gene::sus", "gene", "sus")],
    ])
    bundle = train_bundle(
        X=X, labels_by_drug={"drug_a": labels}, sample_ids=sample_ids,
        split_by_sample=splits, group_by_sample=groups, feature_schema=schema,
        drug_panel=[{"id": "drug_a", "display_name": "Drug A"}], output_dir=tmp_path / "bundle",
        label_policy={"resistant_values": ["Resistant"], "susceptible_values": ["Susceptible"]},
    )
    manifest = json.loads((bundle / "bundle_manifest.json").read_text())
    assert manifest["label_policy"]["resistant_values"] == ["Resistant"]
    engine = PredictionEngine(bundle)
    predictions, unknown = engine.predict_findings(
        [NormalizedFinding("gene::res", "gene", "res")], species_id="escherichia_coli")
    assert not unknown
    assert predictions[0].resistance_probability > 0.5
