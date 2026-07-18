from __future__ import annotations

import numpy as np

from .abstention import abstention_metrics


def metrics_by_group(y: np.ndarray, probabilities: np.ndarray, calls: np.ndarray, groups: np.ndarray) -> list[dict]:
    output = []
    for group in sorted(set(groups.tolist())):
        mask = groups == group
        item = {"group_id": str(group), "sample_count": int(mask.sum()),
                "resistant_count": int(y[mask].sum()),
                "mean_probability": float(np.mean(probabilities[mask])),
                "observed_resistant_fraction": float(np.mean(y[mask])),
                "mean_brier_contribution": float(np.mean((probabilities[mask] - y[mask]) ** 2))}
        item.update(abstention_metrics(y[mask], calls[mask]))
        output.append(item)
    return output

