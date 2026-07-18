from __future__ import annotations

import numpy as np


def abstention_metrics(y: np.ndarray, calls: np.ndarray) -> dict:
    called = calls != -1
    no_call_rate = float(1 - np.mean(called))
    accuracy = float(np.mean(calls[called] == y[called])) if called.any() else None
    return {"no_call_rate": no_call_rate, "coverage": 1 - no_call_rate,
            "accuracy_on_called": accuracy, "called_count": int(called.sum()),
            "no_call_count": int((~called).sum())}

