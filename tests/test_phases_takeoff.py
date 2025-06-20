import json
import os
from datetime import datetime, timedelta
import pytest

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.phases.takeoff import TakeoffDetector
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.utils.parsing import parse_timestamp

def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)

@pytest.fixture
def detector():
    return TakeoffDetector()

@pytest.fixture
def context():
    return FlightDetectorContext()    

def test_takeoff_with_flaps_then_flaps_to_zero(detector, context):
    base = datetime(2025, 6, 17, 10, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), onGround=True, Heading=40),
        make_event(base + timedelta(seconds=5), onGround=True, Heading=50),  # start
        make_event(base + timedelta(seconds=10), onGround=True, Heading=51),
        make_event(base + timedelta(seconds=20), onGround=False, Heading=52, Flaps=5, Gear="Down"),
        make_event(base + timedelta(seconds=30), Flaps=2),
        make_event(base + timedelta(seconds=40), Flaps=0),  # end
    ]
    start, end = detector.detect(events, None, None, context)
    assert start == base + timedelta(seconds=5)
    assert end == base + timedelta(seconds=40)

def test_takeoff_with_flaps_zero_then_gear_up(detector, context):
    base = datetime(2025, 6, 17, 11, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), onGround=True, Heading=70),
        make_event(base + timedelta(seconds=5), onGround=True, Heading=90),
        make_event(base + timedelta(seconds=10), onGround=True, Heading=120, Flaps=0, Gear="Down"),  # start
        make_event(base + timedelta(seconds=15), onGround=False, Heading=122),
        make_event(base + timedelta(seconds=20), Heading=125),
        make_event(base + timedelta(seconds=25), Gear="Up"),  # end
    ]
    start, end = detector.detect(events, None, None, context)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=25)

def test_takeoff_with_no_flaps_or_gear_change_fallback_to_1min(detector, context):
    base = datetime(2025, 6, 17, 12, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), onGround=True, Heading=200),  # start
        make_event(base + timedelta(seconds=10), onGround=False, Heading=200, Flaps=0, Gear="Down"),
        make_event(base + timedelta(seconds=30), Heading=205),
        make_event(base + timedelta(seconds=61), Heading=210),  # end
    ]
    start, end = detector.detect(events, None, None, context)
    assert start == base + timedelta(seconds=0)
    assert end == base + timedelta(seconds=61)

def test_takeoff_no_onGround_false_returns_none(detector, context):
    base = datetime(2025, 6, 17, 14, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), onGround=True, Heading=250),
        make_event(base + timedelta(seconds=5), Heading=250),
        make_event(base + timedelta(seconds=10), Flaps=5),
    ]
    result = detector.detect(events, None, None, context)
    assert result is None


@pytest.mark.parametrize("filename, expected_start, expected_end", [
    ("LEPA-LEPP-737.json", "2025-06-14T17:17:51.8989784", "2025-06-14T17:19:23.8887749"),
    ("LEPP-LEMG-737.json", "2025-06-14T23:49:32.9580634", "2025-06-14T23:51:14.9566859"),
    ("LPMA-Circuits-737.json", "2025-06-02T21:48:07.7370288", "2025-06-02T21:49:49.7389212"),
    ("UHMA-PAOM-B350.json", "2025-06-15T22:20:02.5822203", "2025-06-15T22:20:50.5779508"),
    ("UHPT-UHMA-B350.json", "2025-06-15T18:17:38.8254324", "2025-06-15T18:18:16.828107"),
    ("UHPT-UHMA-SF34.json", "2025-06-05T13:08:25.2219923", "2025-06-05T13:09:09.2296981"), #TODO: Bajar tolerancia heading caja negra
    ("UHSH-UHMM-B350.json", "2025-05-17T17:55:53.265564", "2025-05-17T17:57:09.2445871"),
])    
def test_detect_takeoff_phase_from_real_files(filename, expected_start, expected_end, detector, context):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = detector.detect(events, None, None, context)

    assert result is not None, f"Takeoff not detected in {filename}"
    start, end = result

    expected_start_dt = parse_timestamp(expected_start)
    expected_end_dt = parse_timestamp(expected_end)

    assert start == expected_start_dt, f"Incorrect start for takeoff in {filename}"
    assert end == expected_end_dt, f"Incorrect end for takeoff in {filename}"    