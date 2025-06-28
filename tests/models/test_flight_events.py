import pytest

from mam_analyzer.models.flight_events import FlightEvent


@pytest.fixture
def empty_event() -> FlightEvent:
    return FlightEvent.from_json({
        "Timestamp": "2025-01-01T12:00:00Z"
    })

@pytest.fixture
def only_changes_event() -> FlightEvent:
    return FlightEvent.from_json({
        "Timestamp": "2025-01-01T12:00:00Z",
        "Changes": {"Engine 1": "On", "Flaps": "10"},
    })

@pytest.fixture
def full_event() -> FlightEvent:
    return FlightEvent.from_json({
        "Timestamp": "2025-01-01T12:00:00Z",
        "Changes": {
            "Latitude": "32,69286",
            "Longitude": "-16,7776",
            "onGround": "True",
            "Altitude": "190",
            "AGLAltitude": "0",
            "Altimeter": "-74",
            "VSFpm": "0",
            "Heading": "140",
            "GSKnots": "0",
            "IASKnots": "0",
            "QNHSet": "1013",
            "Flaps": "0",
            "Gear": "Down",
            "FuelKg": "9535,299668470565",
            "Squawk": "2000",
            "AP": "Off",
            "Engine 1": "Off",
            "Engine 2": "Off"
        },
    })    
        

def test_full_event_with_empty(empty_event):
    assert empty_event.is_full_event() == False

def test_full_event_with_only_changes(only_changes_event):
    assert only_changes_event.is_full_event() == False

def test_full_event_with_full_info(full_event):
    assert full_event.is_full_event() == True       

