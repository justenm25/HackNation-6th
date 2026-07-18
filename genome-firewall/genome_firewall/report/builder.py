from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..types import DrugPrediction, PredictionReport


def build_report(*, sample_id: str, input_type: str, species_id: str, predictions: list[DrugPrediction],
                 bundle_id: str, feature_schema_id: str, unknown_features: list[str],
                 fasta_sha256: str | None = None) -> PredictionReport:
    return PredictionReport(
        schema_version="genome-firewall-report-v1", report_id=str(uuid4()),
        sample={"sample_id": sample_id, "input_type": input_type, "fasta_sha256": fasta_sha256,
                "species_expected": species_id, "species_verified": False},
        analysis={"bundle_id": bundle_id, "feature_schema_id": feature_schema_id,
                  "created_at": datetime.now(timezone.utc).isoformat()},
        predictions=predictions,
        quality={"unknown_feature_count": len(unknown_features), "unknown_features": unknown_features,
                 "schema_valid": True, "tool_success": True},
        limitations=["Decision-support output only.", "Species identity was assumed rather than verified.",
                     "Phenotypic susceptibility requires laboratory confirmation."],
    )

