"""Smoke tests for the preprocessing CLI.

These cover argument parsing, index bounds, resume/skip behavior, and malformed cohort
rows. AMRFinder and Mash are never invoked: the one test that exercises a successful run
replaces subprocess.run with a stub that writes the output file the CLI expects.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from genome_firewall.exceptions import InputValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "backend" / "prepare_training_data.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("prepare_training_data", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


prepare = _load_module()


HEADER = "genome_id,fasta_path," + ",".join(prepare.DRUGS)


def write_cohort(path: Path, rows: list[str], header: str = HEADER) -> Path:
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def cohort(tmp_path):
    return write_cohort(tmp_path / "cohort.csv", [
        "g1,g1.fna,Resistant,Susceptible,Susceptible,Resistant",
        "g2,g2.fna,Susceptible,Susceptible,Resistant,Resistant",
    ])


# --------------------------------------------------------------------- argument parsing


def test_parser_requires_a_subcommand():
    with pytest.raises(SystemExit):
        prepare.parser().parse_args([])


def test_amrfinder_arguments_parse_with_expected_types(tmp_path):
    args = prepare.parser().parse_args([
        "amrfinder", "--cohort", str(tmp_path / "c.csv"), "--fasta-root", str(tmp_path),
        "--output", str(tmp_path / "out"), "--index", "3",
    ])
    assert args.command == "amrfinder"
    assert args.index == 3
    assert isinstance(args.cohort, Path)
    # Defaults the cluster wrappers rely on.
    assert args.organism == "Escherichia"
    assert args.executable == "amrfinder"
    assert args.database_dir is None
    assert args.threads_per_task == 1
    assert args.function is prepare.command_amrfinder


def test_amrfinder_requires_cohort_fasta_root_and_output(tmp_path):
    with pytest.raises(SystemExit):
        prepare.parser().parse_args(["amrfinder", "--cohort", str(tmp_path / "c.csv")])


def test_group_and_assemble_expose_their_documented_defaults(tmp_path):
    path = str(tmp_path)
    group = prepare.parser().parse_args([
        "group", "--cohort", path, "--fasta-root", path, "--work-dir", path, "--output", path,
    ])
    assert (group.distance_threshold, group.kmer_size, group.sketch_size) == (0.001, 21, 10000)
    assert group.executable == "mash"

    assemble = prepare.parser().parse_args([
        "assemble", "--cohort", path, "--groups", path, "--amr-dir", path, "--output", path,
    ])
    assert (assemble.split_trials, assemble.seed) == (250, 42)
    assert assemble.schema_version == "gf-amr-v1"


# ------------------------------------------------------------------ malformed cohorts


def test_cohort_missing_a_drug_column_is_rejected(tmp_path):
    path = write_cohort(tmp_path / "c.csv", ["g1,g1.fna,Resistant,Susceptible,Susceptible"],
                        header="genome_id,fasta_path,ciprofloxacin,ceftriaxone,gentamicin")
    with pytest.raises(InputValidationError, match="Cohort requires columns"):
        prepare.load_cohort(path)


def test_cohort_with_only_a_header_is_rejected(tmp_path):
    with pytest.raises(InputValidationError, match="Cohort requires columns"):
        prepare.load_cohort(write_cohort(tmp_path / "c.csv", []))


def test_duplicate_genome_ids_are_rejected(tmp_path):
    path = write_cohort(tmp_path / "c.csv", [
        "g1,g1.fna,Resistant,Susceptible,Susceptible,Resistant",
        "g1,other.fna,Susceptible,Susceptible,Resistant,Resistant",
    ])
    with pytest.raises(InputValidationError, match="unique and non-empty"):
        prepare.load_cohort(path)


def test_blank_genome_id_is_rejected(tmp_path):
    path = write_cohort(tmp_path / "c.csv", [",g1.fna,Resistant,Susceptible,Susceptible,Resistant"])
    with pytest.raises(InputValidationError, match="unique and non-empty"):
        prepare.load_cohort(path)


def test_valid_cohort_loads_every_row(cohort):
    rows = prepare.load_cohort(cohort)
    assert [row["genome_id"] for row in rows] == ["g1", "g2"]


# ---------------------------------------------------------------------- index bounds


@pytest.mark.parametrize("index", [-1, 2, 99])
def test_index_outside_the_cohort_is_rejected(cohort, tmp_path, index, monkeypatch):
    monkeypatch.setattr(prepare.subprocess, "run", _forbidden)
    args = prepare.parser().parse_args([
        "amrfinder", "--cohort", str(cohort), "--fasta-root", str(tmp_path),
        "--output", str(tmp_path / "amr"), "--index", str(index),
    ])
    with pytest.raises(InputValidationError, match="outside 0..1"):
        prepare.command_amrfinder(args)


def test_last_valid_index_is_accepted(cohort, tmp_path, monkeypatch, capsys):
    # Index 1 is the final row of a two-row cohort; an off-by-one here would reject it.
    output = tmp_path / "amr"
    output.mkdir()
    (output / "g2.tsv").write_text("x" * 200, encoding="utf-8")
    monkeypatch.setattr(prepare.subprocess, "run", _forbidden)
    args = prepare.parser().parse_args([
        "amrfinder", "--cohort", str(cohort), "--fasta-root", str(tmp_path),
        "--output", str(output), "--index", "1",
    ])
    prepare.command_amrfinder(args)
    assert capsys.readouterr().out.strip() == "1\tg2\tskipped"


# ------------------------------------------------------------------ resume and skip


def _forbidden(*args, **kwargs):
    raise AssertionError("AMRFinder must not be executed by these tests")


def _row(genome_id="g1", fasta="g1.fna"):
    return {"genome_id": genome_id, "fasta_path": fasta}


def test_existing_result_is_skipped_without_running_amrfinder(tmp_path, monkeypatch):
    output_dir = tmp_path / "amr"
    output_dir.mkdir()
    (output_dir / "g1.tsv").write_text("x" * 200, encoding="utf-8")
    monkeypatch.setattr(prepare.subprocess, "run", _forbidden)

    status = prepare.run_amrfinder_one(_row(), tmp_path, output_dir, "amrfinder", None,
                                       "Escherichia", 1)
    assert status == "skipped"


def test_truncated_result_is_not_treated_as_finished(tmp_path, monkeypatch):
    # A short file is what a killed task would leave behind; it must be recomputed, and
    # the missing FASTA proves the CLI got past the skip check.
    output_dir = tmp_path / "amr"
    output_dir.mkdir()
    (output_dir / "g1.tsv").write_text("truncated", encoding="utf-8")
    monkeypatch.setattr(prepare.subprocess, "run", _forbidden)

    with pytest.raises(InputValidationError, match="Missing FASTA"):
        prepare.run_amrfinder_one(_row(), tmp_path, output_dir, "amrfinder", None,
                                  "Escherichia", 1)


def test_missing_fasta_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare.subprocess, "run", _forbidden)
    with pytest.raises(InputValidationError, match="Missing FASTA"):
        prepare.run_amrfinder_one(_row(), tmp_path, tmp_path / "amr", "amrfinder", None,
                                  "Escherichia", 1)


def test_successful_run_publishes_the_output_and_leaves_no_part_file(tmp_path, monkeypatch):
    (tmp_path / "g1.fna").write_text(">c\nACGT\n", encoding="utf-8")
    output_dir = tmp_path / "amr"

    def fake_run(command, **kwargs):
        # The CLI writes to a .part file and renames it only on success.
        target = Path(command[command.index("-o") + 1])
        assert target.suffix == ".part"
        target.write_text("header\n" + "x" * 200, encoding="utf-8")
        return _completed(0)

    monkeypatch.setattr(prepare.subprocess, "run", fake_run)
    status = prepare.run_amrfinder_one(_row(), tmp_path, output_dir, "amrfinder", None,
                                       "Escherichia", 1)

    assert status == "completed"
    assert (output_dir / "g1.tsv").is_file()
    assert not (output_dir / "g1.tsv.part").exists()

    # Re-running now resumes: the published result is skipped, not recomputed.
    monkeypatch.setattr(prepare.subprocess, "run", _forbidden)
    assert prepare.run_amrfinder_one(_row(), tmp_path, output_dir, "amrfinder", None,
                                     "Escherichia", 1) == "skipped"


def test_failed_run_raises_and_discards_the_partial_file(tmp_path, monkeypatch):
    (tmp_path / "g1.fna").write_text(">c\nACGT\n", encoding="utf-8")
    output_dir = tmp_path / "amr"

    def failing_run(command, **kwargs):
        Path(command[command.index("-o") + 1]).write_text("partial", encoding="utf-8")
        return _completed(1, stderr="boom")

    monkeypatch.setattr(prepare.subprocess, "run", failing_run)
    with pytest.raises(RuntimeError, match="AMRFinder failed for g1"):
        prepare.run_amrfinder_one(_row(), tmp_path, output_dir, "amrfinder", None,
                                  "Escherichia", 1)

    assert not (output_dir / "g1.tsv").exists()
    assert not (output_dir / "g1.tsv.part").exists()


def test_organism_and_database_reach_the_amrfinder_command(tmp_path, monkeypatch):
    (tmp_path / "g1.fna").write_text(">c\nACGT\n", encoding="utf-8")
    seen = {}

    def capture(command, **kwargs):
        seen["command"] = command
        Path(command[command.index("-o") + 1]).write_text("x" * 200, encoding="utf-8")
        return _completed(0)

    monkeypatch.setattr(prepare.subprocess, "run", capture)
    prepare.run_amrfinder_one(_row(), tmp_path, tmp_path / "amr", "amrfinder", "/db",
                              "Salmonella", 4)

    command = seen["command"]
    assert command[command.index("-O") + 1] == "Salmonella"
    assert command[command.index("-d") + 1] == "/db"
    assert command[command.index("--threads") + 1] == "4"


class _completed:
    """Stand-in for subprocess.CompletedProcess with only the fields the CLI reads."""

    def __init__(self, returncode: int, stderr: str = ""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""
