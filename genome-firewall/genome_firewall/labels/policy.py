from __future__ import annotations

from typing import Any

from ..exceptions import InputValidationError


def normalize_label(value: Any, *, resistant_values=("R",), susceptible_values=("S",),
                    intermediate_values=("I",), intermediate_policy="exclude") -> int | None:
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip().upper()
    resistant = {str(item).upper() for item in resistant_values}
    susceptible = {str(item).upper() for item in susceptible_values}
    intermediate = {str(item).upper() for item in intermediate_values}
    if normalized in resistant:
        return 1
    if normalized in susceptible:
        return 0
    if normalized in intermediate:
        if intermediate_policy == "exclude":
            return None
        raise InputValidationError("Intermediate labels require an explicit multiclass implementation")
    raise InputValidationError(f"Unknown phenotype label: {value!r}")
