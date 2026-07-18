from pathlib import Path

from genome_firewall.featurize.amrfinder_parser import parse_amrfinder_tsv


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


# amrfinder_genes.tsv uses AMRFinderPlus 3.x column names ("Gene symbol", "Element
# subtype"); amrfinder_point_mutations.tsv uses the 4.x names ("Element symbol", "Subtype")
# emitted by the version pinned in this repo. The parser accepts either spelling of the
# symbol column, so both generations are covered.


def test_gene_fixture_normalizes_gene_rows_and_drops_unnamed_ones():
    findings = parse_amrfinder_tsv(FIXTURES / "amrfinder_genes.tsv")

    assert [f.feature_id for f in findings] == ["gene::blaTEM-1", "gene::tetA", "gene::sul1"]
    assert {f.kind for f in findings} == {"gene"}
    assert all(f.mutation is None for f in findings)

    blatem = findings[0]
    assert blatem.gene_symbol == "blaTEM-1"
    assert blatem.sequence_name == "synthetic_contig_1"
    assert blatem.method == "EXACTX"
    assert blatem.element_subtype == "AMR"
    assert blatem.raw["Class"] == "BETA-LACTAM"


def test_point_mutation_fixture_splits_gene_and_amino_acid_change():
    findings = parse_amrfinder_tsv(FIXTURES / "amrfinder_point_mutations.tsv")

    assert [f.feature_id for f in findings] == [
        "mutation::gyrA::S83L",
        "mutation::parC::S80I",
        "gene::tetA",
    ]

    gyra = findings[0]
    assert gyra.kind == "point_mutation"
    assert (gyra.gene_symbol, gyra.mutation) == ("gyrA", "S83L")
    assert gyra.method == "POINTX"
    assert gyra.sequence_name == "synthetic_contig_1"
    # Current behavior, reported to Codex as C-002 follow-up: the parser reads "Element
    # AMRFinderPlus 4.x renamed "Element subtype" to "Subtype"; both are accepted.
    # even though the row carries POINT. The subtype is not used for feature_id, so
    # detection is unaffected.
    assert gyra.element_subtype == "POINT"
    assert gyra.raw["Subtype"] == "POINT"

    # A plain acquired-gene row in the same file is still parsed as a gene.
    assert findings[2].kind == "gene"
    assert findings[2].mutation is None


def test_parsing_is_deterministic_across_repeated_reads():
    path = FIXTURES / "amrfinder_point_mutations.tsv"
    assert [f.feature_id for f in parse_amrfinder_tsv(path)] == [
        f.feature_id for f in parse_amrfinder_tsv(path)
    ]
