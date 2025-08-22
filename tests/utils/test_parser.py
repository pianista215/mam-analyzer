from src.mam_analyzer import parser
from mam_analyzer.models.flight_events import FlightEvent

def test_load_flight_data():
    data = parser.load_flight_data("data/UHSH-UHMM-B350.json")

    # Debe ser una lista
    assert isinstance(data, list)

    # Debe contener FlightEvent
    assert all(isinstance(ev, FlightEvent) for ev in data)

    # Debe tener al menos un evento
    assert len(data) > 0

    # El primero debe tener un timestamp válido
    assert hasattr(data[0], "timestamp")
    assert data[0].timestamp is not None
