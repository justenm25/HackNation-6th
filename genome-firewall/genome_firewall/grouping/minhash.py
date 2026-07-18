from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Mapping

from ..exceptions import InputValidationError
from .clustering import connected_components


def compute_mash_groups(fasta_by_sample: Mapping[str, str | Path], *, distance_threshold: float = 0.001,
                        kmer_size: int = 21, sketch_size: int = 10000,
                        executable: str = "mash") -> tuple[dict[str, str], list[tuple[str, str, float]]]:
    if not 0 <= distance_threshold <= 1:
        raise InputValidationError("Mash distance threshold must be between 0 and 1")
    samples = sorted(fasta_by_sample)
    if not samples:
        raise InputValidationError("No FASTAs provided for grouping")
    for sample, path in fasta_by_sample.items():
        if not Path(path).is_file():
            raise InputValidationError(f"Missing FASTA for {sample}: {path}")
    with tempfile.TemporaryDirectory(prefix="genome-firewall-mash-") as temp:
        prefix = Path(temp) / "genomes"
        command = [executable, "sketch", "-k", str(kmer_size), "-s", str(sketch_size), "-o", str(prefix)]
        command.extend(str(fasta_by_sample[sample]) for sample in samples)
        _run(command)
        output = _run([executable, "dist", str(prefix) + ".msh", str(prefix) + ".msh"])
    path_to_sample = {str(Path(path)): sample for sample, path in fasta_by_sample.items()}
    path_to_sample.update({str(Path(path).resolve()): sample for sample, path in fasta_by_sample.items()})
    edges: list[tuple[str, str, float]] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) < 3:
            continue
        left, right = path_to_sample.get(fields[0]), path_to_sample.get(fields[1])
        distance = float(fields[2])
        if left and right and left != right and distance <= distance_threshold:
            edges.append((left, right, distance))
    groups = connected_components(samples, ((left, right) for left, right, _ in edges))
    return groups, edges


def _run(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise InputValidationError(f"Could not run {command[0]}: {exc}") from exc
    if result.returncode:
        raise InputValidationError(f"{' '.join(command[:2])} failed: {result.stderr[-2000:]}")
    return result.stdout

