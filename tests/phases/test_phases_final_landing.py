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
        make_event(base + timedelta(seconds=0), heading=90),
        make_event(base + timedelta(seconds=5), heading=91),
        make_event(base + timedelta(seconds=10), heading=90, LandingVSFpm=-300),  # touch
        make_event(base + timedelta(seconds=15), heading=92),
        make_event(base + timedelta(seconds=20), heading=130),  # change > 8°
        make_event(base + timedelta(seconds=25), heading=140),
    ]
    start, end = detector.detect(events, None, None, context)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=15)  # justo antes del cambio

def test_landing_no_heading_change_uses_last_event(detector, context):
    base = datetime(2025, 6, 23, 12, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), heading=85),
        make_event(base + timedelta(seconds=10), heading=86, LandingVSFpm=-250),  # touch
        make_event(base + timedelta(seconds=20), heading=86),
        make_event(base + timedelta(seconds=30), heading=84),
        make_event(base + timedelta(seconds=40), heading=86),
    ]
    start, end = detector.detect(events, None, None, context)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=40)

def test_landing_not_detected_without_vs(detector, context):
    base = datetime(2025, 6, 23, 14, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), heading=100),
        make_event(base + timedelta(seconds=5), heading=105),
        make_event(base + timedelta(seconds=10), heading=110),
    ]
    result = detector.detect(events, None, None, context)
    assert result is None

@pytest.mark.parametrize("filename, expected_start, expected_end", [
    ("LEPA-LEPP-737.json", "2025-06-14T17:03:35.5975269", "2025-06-14T17:07:39.4791104"),
    ("LEPP-LEMG-737.json", "2025-06-14T23:26:04.9623655", "2025-06-14T23:46:28.9605062"),
    ("LPMA-Circuits-737.json", "2025-06-02T21:17:25.7327066", "2025-06-02T21:39:57.7415421"),
    ("UHMA-PAOM-B350.json", "2025-06-15T21:57:38.5719388", "2025-06-15T22:16:58.5783802"),
    ("UHPT-UHMA-B350.json", "2025-06-15T17:58:20.8040915", "2025-06-15T18:12:32.8254948"),
    ("UHPT-UHMA-SF34.json", "2025-06-05T12:59:29.2149344", "2025-06-05T13:03:33.2361648"),
    ("UHSH-UHMM-B350.json", "2025-05-17T17:35:51.2435736", "2025-05-17T17:52:11.2488295"),
    ("PAOM-PANC-B350-fromtaxi.json", "None", "None"),
])
def test_landing_detects_from_real_files(filename, expected_start, expected_end, context):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = detector.detect(events, None, None, context)

    assert result is not None, f"Landing not detected in {filename}"
    start, end = result
    assert isinstance(start, datetime)
    assert isinstance(end, datetime)
    assert start < end
