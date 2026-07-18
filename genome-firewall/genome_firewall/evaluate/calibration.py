from __future__ import annotations

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss


def calibration_metrics(y: np.ndarray, probabilities: np.ndarray, *, bins: int = 10) -> dict:
    count = max(2, min(bins, len(y)))
    observed, predicted = calibration_curve(y, probabilities, n_bins=count, strategy="quantile")
    return {"brier_score": float(brier_score_loss(y, probabilities)),
            "reliability_curve": [{"mean_predicted": float(p), "observed_resistant_fraction": float(o)}
                                  for o, p in zip(observed, predicted)]}

