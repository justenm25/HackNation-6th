from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import joblib
import numpy as np
from scipy.sparse import spmatrix

from ..calibrate.calibrators import ProbabilityCalibrator
from ..calibrate.thresholds import select_thresholds
from ..exceptions import InputValidationError
from ..featurize.schema import FeatureSchema
from ..grouping.leakage_audit import audit_split_homology
from .logistic import tune_logistic_model


def train_bundle(*, X: spmatrix, labels_by_drug: Mapping[str, np.ndarray], sample_ids: list[str],
                 split_by_sample: Mapping[str, str], group_by_sample: Mapping[str, str],
                 feature_schema: FeatureSchema, drug_panel: list[dict], output_dir: str | Path,
                 calibration_method: str = "sigmoid", random_state: int = 42,
                 label_policy: Mapping[str, object] | None = None) -> Path:
    audit = audit_split_homology(split_by_sample, group_by_sample)
    if X.shape != (len(sample_ids), len(feature_schema.columns)):
        raise InputValidationError("Feature matrix shape does not match samples/schema")
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise InputValidationError(f"Refusing to overwrite non-empty bundle: {output}")
    (output / "models").mkdir(parents=True, exist_ok=True)
    (output / "calibrators").mkdir(exist_ok=True)
    feature_schema.save(output / "feature_schema.json")
    sample_index = {sample: i for i, sample in enumerate(sample_ids)}
    thresholds, training_details = {}, {}
    for drug in drug_panel:
        drug_id = drug["id"]
        labels = np.asarray(labels_by_drug[drug_id], dtype=float)
        train_idx = np.array([sample_index[s] for s in sample_ids if split_by_sample[s] == "train" and not np.isnan(labels[sample_index[s]])])
        cal_idx = np.array([sample_index[s] for s in sample_ids if split_by_sample[s] == "calibration" and not np.isnan(labels[sample_index[s]])])
        if not len(train_idx) or not len(cal_idx):
            raise InputValidationError(f"Drug {drug_id} lacks train or calibration labels")
        y_train, y_cal = labels[train_idx].astype(int), labels[cal_idx].astype(int)
        groups = np.array([group_by_sample[sample_ids[i]] for i in train_idx])
        model, tuning = tune_logistic_model(X[train_idx], y_train, groups, random_state=random_state)
        raw_cal = model.predict_proba(X[cal_idx])[:, 1]
        calibrator = ProbabilityCalibrator(calibration_method).fit(raw_cal, y_cal)
        calibrated = calibrator.predict(raw_cal)
        thresholds[drug_id] = select_thresholds(calibrated, y_cal)
        joblib.dump(model, output / "models" / f"{drug_id}.joblib")
        joblib.dump(calibrator, output / "calibrators" / f"{drug_id}.joblib")
        training_details[drug_id] = {"train_samples": len(train_idx), "calibration_samples": len(cal_idx),
                                     "tuning": tuning, "calibration_method": calibration_method}
    _write_json(output / "thresholds.json", thresholds)
    _write_json(output / "leakage_audit.json", audit)
    manifest = {"bundle_schema_version": "genome-firewall-bundle-v1",
                "created_at": datetime.now(timezone.utc).isoformat(), "random_state": random_state,
                "feature_schema_id": feature_schema.schema_id, "drug_panel": drug_panel,
                "label_policy": dict(label_policy or {}),
                "training": training_details}
    _write_json(output / "bundle_manifest.json", manifest)
    return output


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
