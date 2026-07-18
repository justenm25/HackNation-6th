from __future__ import annotations

import numpy as np

from ..exceptions import InputValidationError


def select_thresholds(probabilities: np.ndarray, y: np.ndarray, *,
                      resistant_candidates=(0.7, 0.8, 0.9), susceptible_candidates=(0.05, 0.1, 0.2),
                      minimum_called_accuracy: float = 0.9) -> dict:
    probabilities, labels = np.asarray(probabilities), np.asarray(y)
    candidates = []
    for resistant in resistant_candidates:
        for susceptible in susceptible_candidates:
            if susceptible >= resistant:
                continue
            called = (probabilities >= resistant) | (probabilities <= susceptible)
            if not called.any():
                continue
            predictions = (probabilities[called] >= resistant).astype(int)
            accuracy = float(np.mean(predictions == labels[called]))
            coverage = float(np.mean(called))
            candidates.append({"resistant": resistant, "susceptible": susceptible,
                               "accuracy_on_called": accuracy, "coverage": coverage})
    eligible = [item for item in candidates if item["accuracy_on_called"] >= minimum_called_accuracy]
    if not eligible:
        raise InputValidationError("No threshold pair meets minimum called accuracy")
    best = max(eligible, key=lambda item: (item["coverage"], item["accuracy_on_called"]))
    return {"resistant_threshold": best["resistant"], "susceptible_threshold": best["susceptible"],
            "selection": best, "candidates": candidates}

