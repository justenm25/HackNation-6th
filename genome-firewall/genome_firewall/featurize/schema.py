from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
from scipy.sparse import csr_matrix

from ..exceptions import SchemaMismatchError
from ..types import NormalizedFinding


@dataclass(frozen=True)
class FeatureSchema:
    schema_version: str
    columns: tuple[str, ...]
    schema_id: str
    unknown_feature_policy: str = "record_and_ignore"

    @classmethod
    def fit(cls, samples: Iterable[Iterable[NormalizedFinding]], schema_version: str = "gf-amr-v1") -> "FeatureSchema":
        columns = tuple(sorted({finding.feature_id for sample in samples for finding in sample}))
        digest = hashlib.sha256("\n".join(columns).encode()).hexdigest()[:16]
        return cls(schema_version, columns, f"{schema_version}-{digest}")

    def transform(self, findings: Iterable[NormalizedFinding]) -> tuple[csr_matrix, list[str]]:
        index = {name: i for i, name in enumerate(self.columns)}
        present = {finding.feature_id for finding in findings}
        known = sorted(index[name] for name in present if name in index)
        values = np.ones(len(known), dtype=np.uint8)
        matrix = csr_matrix((values, ([0] * len(known), known)), shape=(1, len(self.columns)), dtype=np.uint8)
        return matrix, sorted(present - index.keys())

    def validate_columns(self, columns: Sequence[str]) -> None:
        if tuple(columns) != self.columns:
            missing = sorted(set(self.columns) - set(columns))
            extra = sorted(set(columns) - set(self.columns))
            raise SchemaMismatchError(f"Feature columns mismatch; missing={missing}, extra={extra}")

    def save(self, path: str | Path) -> None:
        payload = {"schema_version": self.schema_version, "schema_id": self.schema_id,
                   "unknown_feature_policy": self.unknown_feature_policy,
                   "columns": [{"index": i, "feature_id": value} for i, value in enumerate(self.columns)]}
        Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "FeatureSchema":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        indexed = sorted(payload["columns"], key=lambda item: item["index"])
        return cls(payload["schema_version"], tuple(item["feature_id"] for item in indexed),
                   payload["schema_id"], payload.get("unknown_feature_policy", "record_and_ignore"))

