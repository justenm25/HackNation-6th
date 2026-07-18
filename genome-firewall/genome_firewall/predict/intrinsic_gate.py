from __future__ import annotations

from typing import Iterable


def matching_intrinsic_rule(rules: Iterable[dict], species_id: str, drug_id: str) -> dict | None:
    for rule in rules:
        if (rule.get("enabled", True) and rule.get("species") == species_id
                and rule.get("drug") == drug_id and rule.get("outcome") == "likely_to_fail"):
            return rule
    return None

