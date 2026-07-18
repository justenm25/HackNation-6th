from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .exceptions import InputValidationError


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise InputValidationError(f"Expected mapping in config: {path}")
    return value


def validate_project_config(config: dict[str, Any]) -> None:
    required = {"species", "drug_panel", "features", "grouping", "labels", "calibration", "calling"}
    missing = sorted(required - config.keys())
    if missing:
        raise InputValidationError(f"Config missing sections: {missing}")
    ids = [drug.get("id") for drug in config["drug_panel"]]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise InputValidationError("Drug IDs must be non-empty and unique")

