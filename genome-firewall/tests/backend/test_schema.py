from genome_firewall.featurize.schema import FeatureSchema
from genome_firewall.types import NormalizedFinding


def finding(name):
    return NormalizedFinding(feature_id=name, kind="gene", gene_symbol=name.split("::")[1])


def test_schema_is_deterministic_and_records_unknowns(tmp_path):
    schema = FeatureSchema.fit([[finding("gene::tetA")], [finding("gene::blaA")]])
    assert schema.columns == ("gene::blaA", "gene::tetA")
    matrix, unknown = schema.transform([finding("gene::tetA"), finding("gene::new")])
    assert matrix.toarray().tolist() == [[0, 1]]
    assert unknown == ["gene::new"]
    schema.save(tmp_path / "schema.json")
    assert FeatureSchema.load(tmp_path / "schema.json") == schema

