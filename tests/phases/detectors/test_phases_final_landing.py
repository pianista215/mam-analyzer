import json
import os
from datetime import datetime, timedelta
import pytest

from mam_analyzer.phases.detectors.final_landing import FinalLandingDetector
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.utils.parsing import parse_timestamp

BASE_CHANGES_FULL_EVENT_WITHOUT_HEADING_ONGROUND = {
    "Latitude": "32,69286",
    "Longitude": "-16,7776",
    "Altitude": "190",
    "AGLAltitude": "0",
    "Altimeter": "-74",
    "VSFpm": "0",
    "GSKnots": "0",
    "IASKnots": "0",
    "QNHSet": "1013",
    "Flaps": "0",
    "Gear": "Down",
    "FuelKg": "9535,299668470565",
    "Squawk": "2000",
    "AP": "Off",
}

def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)

def make_full_event(timestamp, **extra_changes) -> FlightEvent:
    changes = BASE_CHANGES_FULL_EVENT_WITHOUT_HEADING_ONGROUND.copy()
    changes.update({k: str(v) for k, v in extra_changes.items()})
    return FlightEvent.from_json({
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": changes,
    })


@pytest.fixture
def detector():
    return FinalLandingDetector()

def test_landing_detects_phase_with_heading_change(detector):
    base = datetime(2025, 6, 23, 10, 0, 0)
    events = [
        make_full_event(base + timedelta(seconds=0), Heading=90, onGround=False),
        make_event(base + timedelta(seconds=5), Heading=91),
        make_full_event(base + timedelta(seconds=10), Heading=90, LandingVSFpm=-300, onGround=True),  # touch
        make_event(base + timedelta(seconds=15), Heading=92),
        make_event(base + timedelta(seconds=20), Heading=130),  # change > 8°
        make_event(base + timedelta(seconds=25), Heading=140),
    ]
    start, end = detector.detect(events, None, None)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=15)  # justo antes del cambio

def test_landing_no_heading_change_uses_last_event(detector):
    base = datetime(2025, 6, 23, 12, 0, 0)
    events = [
        make_full_event(base + timedelta(seconds=0), Heading=85, onGround=False),
        make_full_event(base + timedelta(seconds=10), Heading=86, LandingVSFpm=-250, onGround=True),  # touch
        make_event(base + timedelta(seconds=20), Heading=86),
        make_event(base + timedelta(seconds=30), Heading=84),
        make_event(base + timedelta(seconds=40), Heading=86),
    ]
    start, end = detector.detect(events, None, None)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=40)

def test_landing_not_detected_without_vs(detector):
    base = datetime(2025, 6, 23, 14, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), Heading=100),
        make_event(base + timedelta(seconds=5), Heading=105),
        make_event(base + timedelta(seconds=10), Heading=110),
    ]
    result = detector.detect(events, None, None)
    assert result is None

def test_landing_bounces(detector):
    base = datetime(2025, 6, 23, 12, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), Heading=85),
        make_full_event(base + timedelta(seconds=10), Heading=86, LandingVSFpm=-250, onGround=True), # bounce -> final_landing
        make_full_event(base + timedelta(seconds=12), Heading=86, onGround=False),
        make_full_event(base + timedelta(seconds=15), Heading=86, LandingVSFpm=-5, onGround=True), #final touch
        make_event(base + timedelta(seconds=30), Heading=84),
        make_event(base + timedelta(seconds=40), Heading=86),
    ]
    start, end = detector.detect(events, None, None)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=40)

def test_only_last_landing(detector):
    base = datetime(2025, 6, 23, 12, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), Heading=85),
        make_full_event(base + timedelta(seconds=10), Heading=86, LandingVSFpm=-250, onGround=True),
        make_full_event(base + timedelta(seconds=50), Heading=86, onGround=False),
        make_full_event(base + timedelta(seconds=70), Heading=86, LandingVSFpm=-5, onGround=True), #final landing
        make_event(base + timedelta(seconds=80), Heading=84),
        make_event(base + timedelta(seconds=90), Heading=102),
    ]
    start, end = detector.detect(events, None, None)
    assert start == base + timedelta(seconds=70)
    assert end == base + timedelta(seconds=80)


def test_final_landing_remains_on_ground(detector):
    base = datetime(2025, 6, 23, 12, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), Heading=85, onGround=False),
        make_full_event(base + timedelta(seconds=10), Heading=86, LandingVSFpm=-250, onGround=True),
        make_event(base + timedelta(seconds=50), Heading=86),
        make_full_event(base + timedelta(seconds=70), Heading=86, onGround=False),
        make_event(base + timedelta(seconds=80), Heading=86),
    ]
    result = detector.detect(events, None, None)
    assert result is None, f"Landing doesn't remain on ground"    

@pytest.mark.parametrize("filename, expected_start, expected_end", [
    ("LEPA-LEPP-737.json", "2025-06-14T18:22:03.8839814", "2025-06-14T18:22:43.8757681"),
    ("LEPP-LEMG-737.json", "2025-06-15T01:08:58.9593068", "2025-06-15T01:09:24.96811"),
    ("LPMA-Circuits-737.json", "2025-06-02T22:13:43.7386248", "2025-06-02T22:14:05.7377146"),
    ("UHMA-PAOM-B350.json", "2025-06-16T00:07:26.5753238", "2025-06-16T00:07:44.5761254"),
    ("UHPT-UHMA-B350.json", "2025-06-15T20:01:00.8191063", "2025-06-15T20:03:02.8108667"),
    ("UHPT-UHMA-SF34.json", "2025-06-05T15:05:21.2266523", "2025-06-05T15:07:23.2129155"),
    ("UHSH-UHMM-B350.json", "2025-05-17T19:41:01.243375", "2025-05-17T19:42:55.2530305"),
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-23T00:15:48.5520445", "2025-06-23T00:16:16.5747404"),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:44:13.3164862", "2025-07-04T23:44:13.3164862"),
])
def test_landing_detects_from_real_files(filename, expected_start, expected_end, detector):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = detector.detect(events, None, None)

    if expected_start != 'None' and expected_end != 'None':
        assert result is not None, f"Final landing not detected in {filename}"
        start, end = result

        expected_start_dt = parse_timestamp(expected_start)
        expected_end_dt = parse_timestamp(expected_end)

        assert start == expected_start_dt, f"Incorrect start for final landing in {filename}"
        assert end == expected_end_dt, f"Incorrect end for final landing in {filename}"

    else:
        assert result is None, f"Final landing shouldn't been detected in {filename}"
