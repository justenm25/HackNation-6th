from __future__ import annotations

import numpy as np

from .abstention import abstention_metrics
from .calibration import calibration_metrics
from .classification import classification_metrics
from .group_metrics import metrics_by_group


def evaluate_drug(y: np.ndarray, probabilities: np.ndarray, groups: np.ndarray, *,
                  resistant_threshold: float, susceptible_threshold: float) -> dict:
    y, probabilities, groups = np.asarray(y, dtype=int), np.asarray(probabilities), np.asarray(groups)
    binary = (probabilities >= 0.5).astype(int)
    calls = np.full(len(y), -1, dtype=int)
    calls[probabilities >= resistant_threshold] = 1
    calls[probabilities <= susceptible_threshold] = 0
    return {"sample_count": len(y), "group_count": len(set(groups.tolist())),
            "class_counts": {"resistant": int(y.sum()), "susceptible": int((y == 0).sum())},
            "classification": classification_metrics(y, probabilities, binary),
            "calibration": calibration_metrics(y, probabilities),
            "abstention": abstention_metrics(y, calls),
            "by_group": metrics_by_group(y, probabilities, calls, groups)}

