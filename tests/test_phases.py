from src.mam_analyzer import phases

def test_detect_phases():
    dummy_data = {"events": []}
    result = phases.detect_phases(dummy_data)
    assert isinstance(result, list)
    assert "Cruise" in result