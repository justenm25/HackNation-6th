"""Reproducibly build and download the BV-BRC E. coli AST cohort.

The script accepts only laboratory-method labels, resolves repeated tests per drug,
filters assembly quality, selects a deterministic label-dense cohort, and downloads
compressed FASTA files atomically. All network steps are resumable.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import random
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

import yaml


API = "https://www.bv-brc.org/api"
RQL_SAFE = "(),&="
GENOME_FIELDS = (
    "genome_id", "genome_name", "species", "genome_quality", "genome_status",
    "genome_length", "contigs", "contig_n50", "checkm_completeness",
    "checkm_contamination", "biosample_accession", "sra_accession",
    "genbank_accessions", "collection_year", "isolation_country", "host_group",
)
AST_FIELDS = (
    "genome_id", "genome_name", "antibiotic", "resistant_phenotype", "evidence",
    "laboratory_typing_method", "testing_standard", "testing_standard_year",
    "measurement_sign", "measurement_value", "measurement_unit", "pmid",
)


def request(url: str, *, accept: str, attempts: int = 5):
    headers = {"Accept": accept, "User-Agent": "Genome-Firewall/0.1 public-data-acquisition"}
    for attempt in range(attempts):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120)
        except (urllib.error.URLError, TimeoutError):
            if attempt + 1 == attempts:
                raise
            time.sleep(2 ** attempt)


def download_ast(config: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for drug in config["antibiotics"]:
        output = output_dir / f"bvbrc_ecoli_ast_{drug}.tsv"
        outputs.append(output)
        if output.exists() and output.stat().st_size > 100:
            continue
        query = (
            f"and(eq(taxon_id,{config['taxon_id']}),eq(antibiotic,{drug}),"
            "eq(evidence,\"Laboratory Method\"))"
            f"&select({','.join(AST_FIELDS)})&limit(25000)"
        )
        url = f"{API}/genome_amr/?{urllib.parse.quote(query, safe=RQL_SAFE)}"
        _atomic_download(url, output, "text/tsv", compress=False)
    return outputs


def read_resolved_labels(ast_paths: Iterable[Path], drugs: list[str]) -> tuple[dict, dict]:
    observations: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    names = {}
    for path in ast_paths:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                genome = row["genome_id"]
                drug = row["antibiotic"]
                if drug not in drugs:
                    continue
                observations[genome][drug].add(row["resistant_phenotype"])
                names[genome] = row.get("genome_name", "")
    labels = {}
    for genome, by_drug in observations.items():
        resolved = {}
        for drug in drugs:
            values = by_drug.get(drug, set())
            eligible = values & {"Resistant", "Susceptible"}
            # Any I or contradictory R/S makes this drug missing for this genome.
            resolved[drug] = next(iter(eligible)) if len(eligible) == 1 and values <= eligible else ""
        if any(resolved.values()):
            labels[genome] = resolved
    return labels, names


def fetch_genome_metadata(genome_ids: list[str], cache_path: Path) -> dict[str, dict]:
    cached = {}
    if cache_path.exists():
        cached = {row["genome_id"]: row for row in _read_jsonl(cache_path)}
    missing = [genome for genome in genome_ids if genome not in cached]
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(missing), 100):
        chunk = missing[start:start + 100]
        ids = ",".join(chunk)
        query = f"in(genome_id,({ids}))&select({','.join(GENOME_FIELDS)})&limit(100)"
        url = f"{API}/genome/?{urllib.parse.quote(query, safe='(),&=')}"
        with request(url, accept="application/json") as response:
            rows = json.load(response)
        with cache_path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
                cached[row["genome_id"]] = row
        print(f"metadata {min(start + len(chunk), len(missing))}/{len(missing)}", file=sys.stderr)
    return cached


def passes_quality(row: dict, config: dict) -> bool:
    quality = config["quality"]
    try:
        return (
            row.get("species") == config["species"]
            and row.get("genome_quality") in quality["accepted_genome_quality"]
            and float(row.get("checkm_completeness", 0)) >= quality["minimum_checkm_completeness"]
            and float(row.get("checkm_contamination", 999)) <= quality["maximum_checkm_contamination"]
            and quality["minimum_genome_length"] <= int(row.get("genome_length", 0)) <= quality["maximum_genome_length"]
            and int(row.get("contigs", 999999)) <= quality["maximum_contigs"]
        )
    except (TypeError, ValueError):
        return False


def select_cohort(labels: dict, metadata: dict, config: dict) -> list[str]:
    candidates = [genome for genome in labels if genome in metadata and passes_quality(metadata[genome], config)]
    seed = int(config["cohort"]["random_seed"])
    rng = random.Random(seed)
    tie_breaker = {genome: rng.random() for genome in sorted(candidates)}
    # Prefer samples with more usable drug labels, then use a seeded random order.
    candidates.sort(key=lambda genome: (-sum(bool(value) for value in labels[genome].values()), tie_breaker[genome]))
    return candidates[: int(config["cohort"]["maximum_genomes"])]


def write_cohort(path: Path, selected: list[str], labels: dict, metadata: dict, config: dict) -> None:
    drugs = config["antibiotics"]
    fields = list(GENOME_FIELDS) + drugs + ["fasta_path", "source", "source_snapshot_sha256"]
    source_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for genome in selected:
            row = dict(metadata[genome])
            row.update(labels[genome])
            row.update({"fasta_path": f"fastas/{genome}.fna.gz", "source": "BV-BRC",
                        "source_snapshot_sha256": source_hash})
            writer.writerow(row)


def download_fastas(cohort_path: Path, output_dir: Path, workers: int) -> None:
    with cohort_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    output_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download_one_fasta, row["genome_id"], output_dir / f"{row['genome_id']}.fna.gz"): row["genome_id"] for row in rows}
        for completed, future in enumerate(as_completed(futures), 1):
            genome = futures[future]
            try:
                future.result()
            except Exception as exc:  # keep other resumable downloads running
                failures.append((genome, str(exc)))
            if completed % 50 == 0 or completed == len(futures):
                print(f"fastas {completed}/{len(futures)} failures={len(failures)}", file=sys.stderr)
    if failures:
        failure_path = output_dir.parent / "download_failures.json"
        failure_path.write_text(json.dumps(failures, indent=2) + "\n")
        raise SystemExit(f"{len(failures)} FASTA downloads failed; rerun to resume")


def download_one_fasta(genome_id: str, output: Path) -> None:
    if output.exists() and output.stat().st_size > 100:
        return
    query = f"eq(genome_id,{genome_id})&limit(10000)"
    url = f"{API}/genome_sequence/?{urllib.parse.quote(query, safe='(),&=')}"
    temporary = output.with_suffix(output.suffix + ".part")
    with request(url, accept="application/dna+fasta") as response, gzip.open(temporary, "wb") as target:
        shutil.copyfileobj(response, target)
    if temporary.stat().st_size <= 100:
        temporary.unlink(missing_ok=True)
        raise ValueError("empty FASTA response")
    temporary.replace(output)


def _atomic_download(url: str, output: Path, accept: str, *, compress: bool) -> None:
    temporary = output.with_suffix(output.suffix + ".part")
    with request(url, accept=accept) as response:
        opener = gzip.open if compress else open
        with opener(temporary, "wb") as target:
            shutil.copyfileobj(response, target)
    if temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        raise ValueError(f"empty response for {url}")
    temporary.replace(output)


def _read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "download", "all"])
    parser.add_argument("--config", default="configs/bvbrc_cohort.yaml")
    parser.add_argument("--data-dir", default="data/bvbrc")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    root = Path(args.data_dir)
    cohort_path = root / "cohort.csv"
    if args.command in {"prepare", "all"}:
        ast_paths = download_ast(config, root / "raw")
        labels, _ = read_resolved_labels(ast_paths, config["antibiotics"])
        metadata = fetch_genome_metadata(sorted(labels), root / "raw" / "genome_metadata.jsonl")
        selected = select_cohort(labels, metadata, config)
        write_cohort(cohort_path, selected, labels, metadata, config)
        print(f"selected {len(selected)} genomes -> {cohort_path}")
    if args.command in {"download", "all"}:
        if not cohort_path.exists():
            parser.error(f"cohort missing: {cohort_path}; run prepare first")
        download_fastas(cohort_path, root / "fastas", args.workers)


if __name__ == "__main__":
    main()
