import json
import os
from datetime import datetime, timedelta
import pytest

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.phases.final_landing import FinalLandingDetector
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
    return FinalLandingDetector()

@pytest.fixture
def context():
    return FlightDetectorContext()

def test_landing_detects_phase_with_heading_change(detector, context):
    base = datetime(2025, 6, 23, 10, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), Heading=90),
        make_event(base + timedelta(seconds=5), Heading=91),
        make_event(base + timedelta(seconds=10), Heading=90, LandingVSFpm=-300),  # touch
        make_event(base + timedelta(seconds=15), Heading=92),
        make_event(base + timedelta(seconds=20), Heading=130),  # change > 8°
        make_event(base + timedelta(seconds=25), Heading=140),
    ]
    start, end = detector.detect(events, None, None, context)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=15)  # justo antes del cambio

def test_landing_no_heading_change_uses_last_event(detector, context):
    base = datetime(2025, 6, 23, 12, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), Heading=85),
        make_event(base + timedelta(seconds=10), Heading=86, LandingVSFpm=-250),  # touch
        make_event(base + timedelta(seconds=20), Heading=86),
        make_event(base + timedelta(seconds=30), Heading=84),
        make_event(base + timedelta(seconds=40), Heading=86),
    ]
    start, end = detector.detect(events, None, None, context)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=40)

def test_landing_not_detected_without_vs(detector, context):
    base = datetime(2025, 6, 23, 14, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), Heading=100),
        make_event(base + timedelta(seconds=5), Heading=105),
        make_event(base + timedelta(seconds=10), Heading=110),
    ]
    result = detector.detect(events, None, None, context)
    assert result is None

    # TODO: Think about legacy files (maybe set VS as Landing for test purposes) ?

@pytest.mark.parametrize("filename, expected_start, expected_end", [
    ("LEPA-LEPP-737.json", "2025-06-14T18:22:03.8839814", "2025-06-14T18:22:43.8757681"),
    ("LEPP-LEMG-737.json", "2025-06-15T01:08:58.9593068", "2025-06-15T01:09:24.96811"),
    ("LPMA-Circuits-737.json", "None", "None"), # legacy
    ("UHMA-PAOM-B350.json", "2025-06-16T00:07:26.5753238", "2025-06-16T00:07:44.5761254"),
    ("UHPT-UHMA-B350.json", "2025-06-15T20:01:00.8191063", "2025-06-15T20:03:02.8108667"),
    ("UHPT-UHMA-SF34.json", "None", "None"), #legacy
    ("UHSH-UHMM-B350.json", "None", "None"), #legacy
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-23T00:15:48.5520445", "2025-06-23T00:16:16.5747404"),
])
def test_landing_detects_from_real_files(filename, expected_start, expected_end, detector, context):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = detector.detect(events, None, None, context)

    if expected_start != 'None' and expected_end != 'None':
        assert result is not None, f"Final landing not detected in {filename}"
        start, end = result

        expected_start_dt = parse_timestamp(expected_start)
        expected_end_dt = parse_timestamp(expected_end)

        assert start == expected_start_dt, f"Incorrect start for final landing in {filename}"
        assert end == expected_end_dt, f"Incorrect end for final landing in {filename}"

    else:
        assert result is None, f"Final landing shouldn't been detected in {filename}"
