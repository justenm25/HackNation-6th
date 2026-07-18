from __future__ import annotations

import numpy as np
from scipy.sparse import spmatrix
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import StratifiedGroupKFold

from ..exceptions import InputValidationError


def fit_logistic_model(X: spmatrix, y: np.ndarray, *, C: float = 1.0,
                       class_weight: str | dict | None = None, random_state: int = 42) -> LogisticRegression:
    _validate_binary(y)
    model = LogisticRegression(C=C, solver="liblinear", class_weight=class_weight,
                               random_state=random_state, max_iter=2000)
    return model.fit(X, y)


def tune_logistic_model(X: spmatrix, y: np.ndarray, groups: np.ndarray, *,
                        c_values=(0.01, 0.1, 1.0, 10.0), class_weights=(None, "balanced"),
                        n_splits: int = 5, random_state: int = 42) -> tuple[LogisticRegression, dict]:
    _validate_binary(y)
    if len(y) != len(groups):
        raise InputValidationError("y and groups lengths differ")
    class_group_counts = [len(set(groups[y == label])) for label in (0, 1)]
    folds = min(n_splits, *class_group_counts)
    if folds < 2:
        model = fit_logistic_model(X, y, random_state=random_state)
        return model, {"tuned": False, "reason": "insufficient_independent_groups", "C": 1.0,
                       "class_weight": None}
    cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=random_state)
    results = []
    for C in c_values:
        for weight in class_weights:
            scores = []
            for train_idx, valid_idx in cv.split(X, y, groups):
                model = fit_logistic_model(X[train_idx], y[train_idx], C=C,
                                           class_weight=weight, random_state=random_state)
                scores.append(balanced_accuracy_score(y[valid_idx], model.predict(X[valid_idx])))
            results.append({"C": C, "class_weight": weight, "mean_balanced_accuracy": float(np.mean(scores))})
    best = max(results, key=lambda item: (item["mean_balanced_accuracy"], -abs(np.log10(item["C"]))))
    model = fit_logistic_model(X, y, C=best["C"], class_weight=best["class_weight"], random_state=random_state)
    return model, {"tuned": True, "folds": folds, "best": best, "candidates": results}


def _validate_binary(y: np.ndarray) -> None:
    values = set(np.asarray(y).tolist())
    if values != {0, 1}:
        raise InputValidationError(f"Binary training requires both 0 and 1; got {sorted(values)}")
