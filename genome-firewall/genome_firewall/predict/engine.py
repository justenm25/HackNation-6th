from __future__ import annotations

import json
from pathlib import Path

import joblib

from ..exceptions import InputValidationError
from ..featurize.schema import FeatureSchema
from ..types import DrugPrediction, NormalizedFinding
from .calling import decide_call
from .evidence import classify_evidence
from .intrinsic_gate import matching_intrinsic_rule


class PredictionEngine:
    def __init__(self, bundle_path: str | Path):
        self.bundle = Path(bundle_path)
        self.manifest = self._json("bundle_manifest.json")
        self.schema = FeatureSchema.load(self.bundle / "feature_schema.json")
        if self.manifest["feature_schema_id"] != self.schema.schema_id:
            raise InputValidationError("Bundle manifest and feature schema disagree")
        self.thresholds = self._json("thresholds.json")
        self.marker_map = self._json_optional("marker_drug_map.json", {})
        intrinsic = self._json_optional("intrinsic_rules.json", {"rules": []})
        self.intrinsic_rules = intrinsic.get("rules", [])
        self.models = {drug["id"]: joblib.load(self.bundle / "models" / f"{drug['id']}.joblib")
                       for drug in self.manifest["drug_panel"]}
        self.calibrators = {drug["id"]: joblib.load(self.bundle / "calibrators" / f"{drug['id']}.joblib")
                            for drug in self.manifest["drug_panel"]}

    def predict_findings(self, findings: list[NormalizedFinding], *, species_id: str,
                         marker_free_susceptible_policy: str = "conservative") -> tuple[list[DrugPrediction], list[str]]:
        X, unknown = self.schema.transform(findings)
        predictions = []
        for drug in self.manifest["drug_panel"]:
            drug_id = drug["id"]
            raw = self.models[drug_id].predict_proba(X)[:, 1]
            probability = float(self.calibrators[drug_id].predict(raw)[0])
            category, evidence = classify_evidence(findings, set(self.marker_map.get(drug_id, [])))
            rule = matching_intrinsic_rule(self.intrinsic_rules, species_id, drug_id)
            threshold = self.thresholds[drug_id]
            warnings = [f"unknown_model_feature:{name}" for name in unknown]
            call, source, reasons = decide_call(
                probability, resistant_threshold=threshold["resistant_threshold"],
                susceptible_threshold=threshold["susceptible_threshold"], evidence_category=category,
                marker_free_susceptible_policy=marker_free_susceptible_policy,
                intrinsic_rule=rule, warnings=warnings,
            )
            confidence = probability if call.value == "likely_to_fail" else (1 - probability if call.value == "likely_to_work" else None)
            if rule:
                evidence.insert(0, {"type": "intrinsic_rule", "rule_id": rule.get("id"),
                                    "interpretation": rule.get("reason_code", "intrinsic_resistance")})
            predictions.append(DrugPrediction(
                drug_id=drug_id, drug_name=drug.get("display_name", drug_id), call=call,
                resistance_probability=probability, calibrated_confidence=confidence,
                confidence_semantics="calibrated_probability_of_resistance" if call.value == "likely_to_fail"
                else ("one_minus_calibrated_resistance_probability" if call.value == "likely_to_work" else "not_applicable_for_no_call"),
                evidence_category=category, decision_source=source, evidence=evidence,
                no_call_reasons=reasons, warnings=warnings,
            ))
        return predictions, unknown

    def _json(self, relative: str) -> dict:
        return json.loads((self.bundle / relative).read_text(encoding="utf-8"))

    def _json_optional(self, relative: str, default: dict) -> dict:
        path = self.bundle / relative
        return self._json(relative) if path.exists() else default

