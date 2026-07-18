from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from ..exceptions import InputValidationError


@dataclass
class ProbabilityCalibrator:
    method: str = "sigmoid"
    fitted: object | None = None

    def fit(self, raw_probabilities: np.ndarray, y: np.ndarray) -> "ProbabilityCalibrator":
        probabilities = np.asarray(raw_probabilities, dtype=float)
        labels = np.asarray(y, dtype=int)
        if len(probabilities) != len(labels) or set(labels.tolist()) != {0, 1}:
            raise InputValidationError("Calibration requires aligned samples from both classes")
        if self.method == "sigmoid":
            eps = np.finfo(float).eps
            logits = np.log(np.clip(probabilities, eps, 1 - eps) / np.clip(1 - probabilities, eps, 1 - eps))
            self.fitted = LogisticRegression(solver="lbfgs").fit(logits.reshape(-1, 1), labels)
        elif self.method == "isotonic":
            self.fitted = IsotonicRegression(out_of_bounds="clip").fit(probabilities, labels)
        else:
            raise InputValidationError(f"Unknown calibration method: {self.method}")
        return self

    def predict(self, raw_probabilities: np.ndarray) -> np.ndarray:
        if self.fitted is None:
            raise InputValidationError("Calibrator is not fitted")
        probabilities = np.asarray(raw_probabilities, dtype=float)
        if self.method == "sigmoid":
            eps = np.finfo(float).eps
            logits = np.log(np.clip(probabilities, eps, 1 - eps) / np.clip(1 - probabilities, eps, 1 - eps))
            return self.fitted.predict_proba(logits.reshape(-1, 1))[:, 1]
        return np.asarray(self.fitted.predict(probabilities))

