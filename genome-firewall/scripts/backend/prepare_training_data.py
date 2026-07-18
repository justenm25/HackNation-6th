"""Prepare the downloaded BV-BRC cohort for leakage-safe model training.

Commands:
  amrfinder  Run/resume AMRFinderPlus for one array index or locally in parallel.
  group      Mash-sketch genomes and form threshold-connected genetic groups.
  assemble   Choose a group-safe split and create the canonical sparse dataset.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from sklearn.model_selection import GroupShuffleSplit

from genome_firewall.exceptions import InputValidationError
from genome_firewall.featurize.amrfinder_parser import parse_amrfinder_tsv
from genome_firewall.featurize.matrix import build_canonical_matrix


DRUGS = ("ciprofloxacin", "ceftriaxone", "gentamicin", "ampicillin")


class UnionFind:
    def __init__(self, values):
        self.parent = {value: value for value in values}

    def find(self, value):
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while value != root:
            value, self.parent[value] = self.parent[value], root
        return root

    def union(self, left, right):
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def load_cohort(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"genome_id", "fasta_path", *DRUGS}
    if not rows or not required <= set(rows[0]):
        raise InputValidationError(f"Cohort requires columns: {sorted(required)}")
    ids = [row["genome_id"] for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise InputValidationError("Cohort genome_id values must be unique and non-empty")
    return rows


def run_amrfinder_one(row: dict[str, str], fasta_root: Path, output_dir: Path,
                      executable: str, database_dir: str | None, organism: str,
                      threads_per_task: int) -> str:
    genome_id = row["genome_id"]
    output = output_dir / f"{genome_id}.tsv"
    if output.exists() and output.stat().st_size > 100:
        return "skipped"
    source = fasta_root / row["fasta_path"]
    if not source.is_file():
        raise InputValidationError(f"Missing FASTA: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tsv.part")
    with tempfile.TemporaryDirectory(prefix=f"gf-amr-{genome_id}-") as temp:
        fasta = Path(temp) / f"{genome_id}.fna"
        if source.suffix == ".gz":
            with gzip.open(source, "rb") as incoming, fasta.open("wb") as outgoing:
                while chunk := incoming.read(1024 * 1024):
                    outgoing.write(chunk)
        else:
            fasta = source
        command = [executable, "-n", str(fasta), "-O", organism, "-o", str(temporary),
                   "--threads", str(threads_per_task)]
        if database_dir:
            command.extend(["-d", database_dir])
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode or not temporary.exists() or temporary.stat().st_size < 100:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"AMRFinder failed for {genome_id}: {result.stderr[-1000:]}")
    temporary.replace(output)
    return "completed"


def command_amrfinder(args) -> None:
    rows = load_cohort(args.cohort)
    if args.index is not None:
        if not 0 <= args.index < len(rows):
            raise InputValidationError(f"Index {args.index} outside 0..{len(rows)-1}")
        status = run_amrfinder_one(rows[args.index], args.fasta_root, args.output,
                                   args.executable, args.database_dir, args.organism,
                                   args.threads_per_task)
        print(f"{args.index}\t{rows[args.index]['genome_id']}\t{status}")
        return
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_amrfinder_one, row, args.fasta_root, args.output,
                               args.executable, args.database_dir, args.organism,
                               args.threads_per_task): row["genome_id"]
                   for row in rows}
        for number, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
            except Exception as exc:
                failures.append((futures[future], str(exc)))
            if number % 50 == 0 or number == len(rows):
                print(f"amrfinder {number}/{len(rows)} failures={len(failures)}", flush=True)
    if failures:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "failures.json").write_text(json.dumps(failures, indent=2) + "\n")
        raise SystemExit(f"{len(failures)} AMRFinder tasks failed; rerun to resume")


def command_group(args) -> None:
    rows = load_cohort(args.cohort)
    sample_ids = [row["genome_id"] for row in rows]
    paths = {row["genome_id"]: (args.fasta_root / row["fasta_path"]).resolve() for row in rows}
    missing = [sample for sample, path in paths.items() if not path.is_file()]
    if missing:
        raise InputValidationError(f"Missing {len(missing)} FASTAs; first={missing[0]}")
    args.work_dir.mkdir(parents=True, exist_ok=True)
    list_path, prefix = args.work_dir / "fastas.txt", args.work_dir / "cohort"
    list_path.write_text("\n".join(str(paths[sample]) for sample in sample_ids) + "\n")
    sketch = Path(str(prefix) + ".msh")
    if not sketch.exists():
        _check([args.executable, "sketch", "-k", str(args.kmer_size), "-s",
                str(args.sketch_size), "-l", str(list_path), "-o", str(prefix)])
    path_to_sample = {str(path): sample for sample, path in paths.items()}
    union = UnionFind(sample_ids)
    edge_path = args.work_dir / "qualifying_edges.csv"
    edge_count = 0
    with edge_path.open("w", newline="") as edge_file:
        writer = csv.writer(edge_file); writer.writerow(["sample_a", "sample_b", "mash_distance"])
        process = subprocess.Popen([args.executable, "dist", str(sketch), str(sketch)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert process.stdout is not None
        for line in process.stdout:
            fields = line.rstrip().split("\t")
            if len(fields) < 3:
                continue
            left, right = path_to_sample.get(fields[0]), path_to_sample.get(fields[1])
            if not left or not right or left >= right:
                continue
            distance = float(fields[2])
            if distance <= args.distance_threshold:
                union.union(left, right); writer.writerow([left, right, distance]); edge_count += 1
        stderr = process.stderr.read() if process.stderr else ""
        if process.wait():
            raise RuntimeError(f"mash dist failed: {stderr[-2000:]}")
    roots = sorted({union.find(sample) for sample in sample_ids})
    group_ids = {root: f"mash_{index:05d}" for index, root in enumerate(roots)}
    with args.output.open("w", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["sample_id", "genetic_group_id"])
        writer.writerows((sample, group_ids[union.find(sample)]) for sample in sample_ids)
    print(f"groups={len(roots)} edges={edge_count} threshold={args.distance_threshold}")


def choose_group_split(rows: list[dict[str, str]], group_by_sample: dict[str, str],
                       trials: int = 250, seed: int = 42) -> dict[str, str]:
    ids = np.array([row["genome_id"] for row in rows])
    groups = np.array([group_by_sample[sample] for sample in ids])
    label = {drug: np.array([row[drug] for row in rows]) for drug in DRUGS}
    best_score, best = float("inf"), None
    for trial in range(trials):
        state = seed + trial
        outer = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=state)
        train_idx, hold_idx = next(outer.split(ids, groups=groups))
        inner = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=state + 10000)
        cal_rel, test_rel = next(inner.split(ids[hold_idx], groups=groups[hold_idx]))
        indices = {"train": train_idx, "calibration": hold_idx[cal_rel], "hidden_test": hold_idx[test_rel]}
        score = 0.0
        for name, idx in indices.items():
            target_fraction = 0.70 if name == "train" else 0.15
            score += abs(len(idx) / len(rows) - target_fraction) * 5
            for drug in DRUGS:
                overall = label[drug][np.isin(label[drug], ["Resistant", "Susceptible"])]
                subset = label[drug][idx]; subset = subset[np.isin(subset, ["Resistant", "Susceptible"])]
                if not len(subset) or len(set(subset)) < 2:
                    score += 100
                else:
                    score += abs(np.mean(subset == "Resistant") - np.mean(overall == "Resistant"))
                    score += abs(len(subset) / max(len(overall), 1) - target_fraction)
        if score < best_score:
            best_score = score
            best = {ids[index]: name for name, idx in indices.items() for index in idx}
    if best is None:
        raise InputValidationError("Could not create a valid grouped split")
    return best


def command_assemble(args) -> None:
    rows = load_cohort(args.cohort)
    with args.groups.open(encoding="utf-8", newline="") as handle:
        group_by_sample = {row["sample_id"]: row["genetic_group_id"] for row in csv.DictReader(handle)}
    if set(group_by_sample) != {row["genome_id"] for row in rows}:
        raise InputValidationError("Group manifest and cohort samples differ")
    missing = [row["genome_id"] for row in rows if not (args.amr_dir / f"{row['genome_id']}.tsv").is_file()]
    if missing:
        raise InputValidationError(f"Missing {len(missing)} AMRFinder results; first={missing[0]}")
    splits = choose_group_split(rows, group_by_sample, trials=args.split_trials, seed=args.seed)
    findings = {row["genome_id"]: parse_amrfinder_tsv(args.amr_dir / f"{row['genome_id']}.tsv") for row in rows}
    sample_ids, matrix, schema, unknown = build_canonical_matrix(findings, splits, schema_version=args.schema_version)
    from scipy.sparse import save_npz
    args.output.mkdir(parents=True, exist_ok=True)
    save_npz(args.output / "X_features.npz", matrix)
    schema.save(args.output / "feature_schema.json")
    row_by_id = {row["genome_id"]: row for row in rows}
    fields = ["sample_id", "split", "genetic_group_id", "fasta_path", *DRUGS]
    with (args.output / "samples.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for sample in sample_ids:
            source = row_by_id[sample]
            writer.writerow({"sample_id": sample, "split": splits[sample],
                             "genetic_group_id": group_by_sample[sample],
                             "fasta_path": source["fasta_path"],
                             **{drug: source[drug] for drug in DRUGS}})
    (args.output / "unknown_features.json").write_text(json.dumps(unknown, indent=2) + "\n")
    print(f"samples={len(sample_ids)} features={matrix.shape[1]} schema={schema.schema_id}")


def _check(command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"{' '.join(command[:2])} failed: {result.stderr[-2000:]}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    amr = commands.add_parser("amrfinder", help="Run/resume AMRFinderPlus")
    amr.add_argument("--cohort", type=Path, required=True); amr.add_argument("--fasta-root", type=Path, required=True)
    amr.add_argument("--output", type=Path, required=True); amr.add_argument("--index", type=int)
    amr.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    amr.add_argument("--threads-per-task", type=int, default=1)
    amr.add_argument("--executable", default="amrfinder"); amr.add_argument("--database-dir")
    amr.add_argument("--organism", default="Escherichia"); amr.set_defaults(function=command_amrfinder)
    group = commands.add_parser("group", help="Compute Mash threshold-connected groups")
    group.add_argument("--cohort", type=Path, required=True); group.add_argument("--fasta-root", type=Path, required=True)
    group.add_argument("--work-dir", type=Path, required=True); group.add_argument("--output", type=Path, required=True)
    group.add_argument("--distance-threshold", type=float, default=0.001)
    group.add_argument("--kmer-size", type=int, default=21); group.add_argument("--sketch-size", type=int, default=10000)
    group.add_argument("--executable", default="mash"); group.set_defaults(function=command_group)
    assemble = commands.add_parser("assemble", help="Build group-safe canonical dataset")
    assemble.add_argument("--cohort", type=Path, required=True); assemble.add_argument("--groups", type=Path, required=True)
    assemble.add_argument("--amr-dir", type=Path, required=True); assemble.add_argument("--output", type=Path, required=True)
    assemble.add_argument("--split-trials", type=int, default=250); assemble.add_argument("--seed", type=int, default=42)
    assemble.add_argument("--schema-version", default="gf-amr-v1"); assemble.set_defaults(function=command_assemble)
    return root


def main() -> None:
    args = parser().parse_args(); args.function(args)


if __name__ == "__main__":
    main()
