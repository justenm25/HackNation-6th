from __future__ import annotations

import argparse
import json

from ..api import predict


EXAMPLES = """\
examples:
  # Assemble-to-call: runs AMRFinderPlus on the genome, then predicts.
  genome-firewall-predict sample.fasta --bundle artifacts/bundle

  # Skip AMRFinderPlus by supplying its TSV output directly.
  genome-firewall-predict sample.tsv --bundle artifacts/bundle --input-format amrfinder_tsv

  # Non-default AMRFinderPlus install and database.
  genome-firewall-predict sample.fasta --bundle artifacts/bundle \\
      --amrfinder /opt/amrfinder/bin/amrfinder --database-dir /opt/amrfinder/data/latest

The JSON report is written to stdout. Each drug is called likely_to_fail, likely_to_work,
or no_call; the tool abstains with no_call whenever the calibrated probability lands in the
band between the bundle's thresholds, and by default it also abstains rather than calling a
drug likely_to_work merely because no resistance marker was found.
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Predict antibiotic resistance for one bacterial genome and print a JSON report.",
        epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", metavar="INPUT",
                        help="Path to the sample: an assembly FASTA, an AMRFinderPlus TSV, "
                             "or a single-row feature JSON (see --input-format)")
    parser.add_argument("--bundle", required=True, metavar="DIR",
                        help="Frozen trained model bundle directory produced by genome-firewall-train")
    parser.add_argument("--input-format", choices=["fasta", "amrfinder_tsv", "feature_matrix"], default="fasta",
                        help="How to read INPUT: 'fasta' runs AMRFinderPlus first, 'amrfinder_tsv' reuses an "
                             "existing AMRFinderPlus report, 'feature_matrix' takes a prebuilt row whose "
                             "schema_id must match the bundle (default: %(default)s)")
    parser.add_argument("--amrfinder", default="amrfinder", metavar="PATH",
                        help="AMRFinderPlus executable to invoke for FASTA input (default: %(default)s)")
    parser.add_argument("--database-dir", metavar="DIR",
                        help="AMRFinderPlus database directory; omit to use the executable's default database")
    args = parser.parse_args()
    report = predict(args.input, bundle_path=args.bundle, input_format=args.input_format,
                     amrfinder_executable=args.amrfinder, amrfinder_database_dir=args.database_dir)
    print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()

