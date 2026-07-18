from __future__ import annotations

from typing import Mapping

from scipy.sparse import vstack

from ..exceptions import InputValidationError
from ..types import NormalizedFinding
from .schema import FeatureSchema


def build_canonical_matrix(findings_by_sample: Mapping[str, list[NormalizedFinding]],
                           split_by_sample: Mapping[str, str], *,
                           schema_version: str = "gf-amr-v1") -> tuple[list[str], object, FeatureSchema, dict[str, list[str]]]:
    sample_ids = sorted(findings_by_sample)
    if set(sample_ids) != set(split_by_sample):
        raise InputValidationError("Findings and split manifests contain different samples")
    train_findings = [findings_by_sample[sample] for sample in sample_ids if split_by_sample[sample] == "train"]
    if not train_findings:
        raise InputValidationError("Cannot fit feature schema without training samples")
    schema = FeatureSchema.fit(train_findings, schema_version=schema_version)
    transformed = [schema.transform(findings_by_sample[sample]) for sample in sample_ids]
    matrix = vstack([item[0] for item in transformed], format="csr")
    unknown = {sample: transformed[i][1] for i, sample in enumerate(sample_ids) if transformed[i][1]}
    return sample_ids, matrix, schema, unknown

