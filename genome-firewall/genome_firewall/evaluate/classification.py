from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, balanced_accuracy_score, recall_score, roc_auc_score


def classification_metrics(y: np.ndarray, probabilities: np.ndarray, predictions: np.ndarray) -> dict:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y, predictions)),
        "resistant_recall": float(recall_score(y, predictions, pos_label=1, zero_division=0)),
        "susceptible_recall": float(recall_score(y, predictions, pos_label=0, zero_division=0)),
        "pr_auc": float(average_precision_score(y, probabilities)),
        "auroc": float(roc_auc_score(y, probabilities)),
    }

