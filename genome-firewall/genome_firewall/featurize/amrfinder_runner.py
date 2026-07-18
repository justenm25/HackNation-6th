from __future__ import annotations

import subprocess
from pathlib import Path

from ..exceptions import InputValidationError


def run_amrfinder(fasta_path: str | Path, output_path: str | Path, *, executable: str = "amrfinder",
                  organism: str = "Escherichia", database_dir: str | None = None,
                  timeout_seconds: int = 300) -> Path:
    fasta, output = Path(fasta_path), Path(output_path)
    if not fasta.is_file():
        raise InputValidationError(f"FASTA not found: {fasta}")
    command = [executable, "-n", str(fasta), "-O", organism, "-o", str(output)]
    if database_dir:
        command.extend(["-d", database_dir])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InputValidationError(f"AMRFinder execution failed: {exc}") from exc
    if result.returncode != 0 or not output.is_file():
        raise InputValidationError(f"AMRFinder failed ({result.returncode}): {result.stderr[-2000:]}")
    return output
