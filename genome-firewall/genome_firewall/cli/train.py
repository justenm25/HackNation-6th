from __future__ import annotations

import argparse

from ..config import load_yaml, validate_project_config
from ..train.dataset import load_prepared_dataset
from ..train.pipeline import train_bundle


EXAMPLES = """\
examples:
  genome-firewall-train --config configs/ecoli.yaml \\
      --dataset data/processed/ecoli --output artifacts/bundle

Only drugs with enabled != false in the config's drug_panel are trained. Models are fit
on the train split, calibrated, and frozen together with the feature schema and decision
thresholds so that predictions stay reproducible.
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and calibrate a Genome Firewall bundle from a canonical prepared dataset.",
        epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, metavar="YAML",
                        help="Species config defining the drug panel, grouping, label policy, and calibration "
                             "(for example configs/ecoli.yaml)")
    parser.add_argument("--dataset", required=True, metavar="DIR",
                        help="Prepared dataset directory from genome-firewall-featurize, containing "
                             "X_features.npz, samples.csv, and feature_schema.json")
    parser.add_argument("--output", required=True, metavar="DIR",
                        help="Directory to write the frozen bundle into: per-drug models and calibrators, "
                             "thresholds.json, and bundle_manifest.json")
    args = parser.parse_args()
    config = load_yaml(args.config)
    validate_project_config(config)
    drug_panel = [drug for drug in config["drug_panel"] if drug.get("enabled", True)]
    dataset = load_prepared_dataset(args.dataset, drug_ids=[drug["id"] for drug in drug_panel],
                                    grouping_config=config["grouping"], label_config=config["labels"])
    train_bundle(X=dataset.X, labels_by_drug=dataset.labels_by_drug, sample_ids=dataset.sample_ids,
                 split_by_sample=dataset.split_by_sample, group_by_sample=dataset.group_by_sample,
                 feature_schema=dataset.feature_schema, drug_panel=drug_panel, output_dir=args.output,
                 calibration_method=config["calibration"].get("method", "sigmoid"))
    print(args.output)


if __name__ == "__main__":
    main()
