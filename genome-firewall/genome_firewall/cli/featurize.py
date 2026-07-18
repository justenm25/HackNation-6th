from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from scipy.sparse import save_npz

from ..featurize.amrfinder_parser import parse_amrfinder_tsv
from ..featurize.matrix import build_canonical_matrix


EXAMPLES = """\
examples:
  genome-firewall-featurize --manifest data/raw/manifest.csv --output data/processed/ecoli

manifest columns:
  sample_id         required, unique per row
  amrfinder_tsv     required, path to that sample's AMRFinderPlus TSV, relative to the manifest
  split             train, calibration, or hidden_test; at least one train row is required
  genetic_group_id  precomputed cluster id keeping related genomes in one split; if any row
                    leaves it blank, every row must instead supply fasta_path so that
                    training can derive groups with mash
  <drug id>         one column per drug in the config panel, holding R / S / I
  fasta_path        only needed when genetic_group_id is not supplied

outputs written into --output:
  X_features.npz        sparse binary sample-by-feature matrix
  feature_schema.json   frozen column order and schema_id, fitted on the train split only
  samples.csv           manifest rows reordered to match the matrix
  unknown_features.json per-sample features absent from the schema and therefore not scored
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert per-sample AMRFinderPlus TSVs into the canonical sparse feature dataset used for training.",
        epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", required=True, metavar="CSV",
                        help="CSV with sample_id, split, amrfinder_tsv, groups, and drug labels; "
                             "TSV paths are resolved relative to this file")
    parser.add_argument("--output", required=True, metavar="DIR",
                        help="Directory to create and fill with the prepared dataset (see below)")
    parser.add_argument("--schema-version", default="gf-amr-v1", metavar="TAG",
                        help="Feature schema version recorded in feature_schema.json and used to derive "
                             "the schema_id that predictions are checked against (default: %(default)s)")
    args = parser.parse_args()
    manifest = Path(args.manifest)
    with manifest.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if not rows or any(not row.get("sample_id") or not row.get("amrfinder_tsv") for row in rows):
        parser.error("Manifest requires sample_id and amrfinder_tsv for every row")
    findings = {row["sample_id"]: parse_amrfinder_tsv(manifest.parent / row["amrfinder_tsv"]) for row in rows}
    splits = {row["sample_id"]: row["split"] for row in rows}
    sample_ids, X, schema, unknown = build_canonical_matrix(findings, splits, schema_version=args.schema_version)
    by_id = {row["sample_id"]: row for row in rows}
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    save_npz(output / "X_features.npz", X)
    schema.save(output / "feature_schema.json")
    with (output / "samples.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(by_id[sample] for sample in sample_ids)
    (output / "unknown_features.json").write_text(json.dumps(unknown, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
