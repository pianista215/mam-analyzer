from src.mam_analyzer import parser

def test_load_flight_data():
    data = parser.load_flight_data("data/UHSH-UHMM-B350.json")
    assert isinstance(data, dict)
    assert "Events" in data