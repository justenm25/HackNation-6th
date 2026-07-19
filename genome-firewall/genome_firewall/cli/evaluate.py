from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np

from ..evaluate.runner import evaluate_drug
from ..train.dataset import load_prepared_dataset


EXAMPLES = """\
examples:
  genome-firewall-evaluate --bundle artifacts/bundle \\
      --dataset data/processed/ecoli --output artifacts/eval/hidden_test.json

Only samples whose split is hidden_test and whose label is present are scored, one drug at
a time, using the thresholds frozen in the bundle. The JSON report covers classification,
calibration, abstention, and group-aware metrics.
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate a frozen bundle on the hidden-test split of a prepared dataset.",
        epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundle", required=True, metavar="DIR",
                        help="Frozen bundle directory from genome-firewall-train; supplies the drug panel, "
                             "models, calibrators, and decision thresholds")
    parser.add_argument("--dataset", required=True, metavar="DIR",
                        help="Prepared dataset directory whose feature schema matches the bundle")
    parser.add_argument("--output", required=True, metavar="JSON",
                        help="Path to write the per-drug metrics report; parent directories are created")
    args = parser.parse_args()
    bundle = Path(args.bundle)
    manifest = json.loads((bundle / "bundle_manifest.json").read_text())
    thresholds = json.loads((bundle / "thresholds.json").read_text())
    drug_ids = [drug["id"] for drug in manifest["drug_panel"]]
    dataset = load_prepared_dataset(args.dataset, drug_ids=drug_ids,
                                    label_config=manifest.get("label_policy"))
    hidden = np.array([dataset.split_by_sample[sample] == "hidden_test" for sample in dataset.sample_ids])
    results = {}
    for drug in drug_ids:
        labels = dataset.labels_by_drug[drug]
        mask = hidden & ~np.isnan(labels)
        model = joblib.load(bundle / "models" / f"{drug}.joblib")
        calibrator = joblib.load(bundle / "calibrators" / f"{drug}.joblib")
        probabilities = calibrator.predict(model.predict_proba(dataset.X[mask])[:, 1])
        groups = np.array([dataset.group_by_sample[sample] for sample, keep in zip(dataset.sample_ids, mask) if keep])
        threshold = thresholds[drug]
        results[drug] = evaluate_drug(labels[mask].astype(int), probabilities, groups,
                                      resistant_threshold=threshold["resistant_threshold"],
                                      susceptible_threshold=threshold["susceptible_threshold"])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
