from app import backend_adapter


def test_default_mode_preserves_collaborator_demo():
    assert backend_adapter.BACKEND_MODE == "collaborator_demo"
    samples = backend_adapter.list_samples()
    assert samples
    result = backend_adapter.predict_genome(None, sample_name=samples[0])
    assert result.predictions
    assert result.species == "Klebsiella pneumoniae"


def test_reliability_is_loaded_from_artifact():
    points = backend_adapter.get_reliability()
    assert points
    assert all("confidence" in point and "accuracy" in point for point in points)
