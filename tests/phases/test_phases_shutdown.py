import json
import os
from datetime import datetime
import pytest

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.shutdown import ShutdownDetector
from mam_analyzer.utils.parsing import parse_timestamp

@pytest.fixture
def shutdown_detector():
    return ShutdownDetector()

@pytest.fixture
def context():
    return FlightDetectorContext()

def test_detect_shutdown_phase_synthetic(shutdown_detector, context):
    raw_events = [
        {"Timestamp": "2025-06-14T17:10:00.000000", "Changes": {"Latitude": "39,020", "Longitude": "2,000"}},
        {"Timestamp": "2025-06-14T17:12:00.000000", "Changes": {"Flaps": "0"}},
        {"Timestamp": "2025-06-14T17:13:00.000000", "Changes": {"Latitude": "39,005", "Longitude": "2,000"}},
        {"Timestamp": "2025-06-14T17:14:00.000000", "Changes": {"Squawk": "1234"}},
        {"Timestamp": "2025-06-14T17:15:00.000000", "Changes": {"Latitude": "39,000", "Longitude": "2,000"}}, # start & end
    ]

    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)
    assert result is not None
    start, end = result
    assert start == parse_timestamp("2025-06-14T17:15:00.000000")
    assert end == parse_timestamp("2025-06-14T17:15:00.000000")


def test_detect_shutdown_phase_synthetic_multiple_events_same_place(shutdown_detector, context):
    raw_events = [
        {"Timestamp": "2025-06-14T17:09:00.000000", "Changes": {"Latitude": "38,000", "Longitude": "2,000"}},
        {"Timestamp": "2025-06-14T17:10:00.000000", "Changes": {"Latitude": "39,000", "Longitude": "2,000"}}, # start
        {"Timestamp": "2025-06-14T17:11:00.000000", "Changes": {"Flaps": "0"}},
        {"Timestamp": "2025-06-14T17:12:00.000000", "Changes": {"Engine 1": "Off"}},
        {"Timestamp": "2025-06-14T17:12:10.000000", "Changes": {"Engine 2": "Off"}},
        {"Timestamp": "2025-06-14T17:13:00.000000", "Changes": {"Latitude": "39,000", "Longitude": "2,000"}},
        {"Timestamp": "2025-06-14T17:14:00.000000", "Changes": {"Squawk": "1234"}},
        {"Timestamp": "2025-06-14T17:15:00.000000", "Changes": {"Latitude": "39,000", "Longitude": "2,000"}}, # end
    ]

    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)
    assert result is not None
    start, end = result
    assert start == parse_timestamp("2025-06-14T17:10:00.000000")
    assert end == parse_timestamp("2025-06-14T17:15:00.000000")    

@pytest.mark.parametrize("filename, expected_start, expected_end", [
    ("LEPA-LEPP-737.json", "", ""),
    ("LEPP-LEMG-737.json", "", ""),
    ("LPMA-Circuits-737.json", "", ""),
    ("UHMA-PAOM-B350.json", "", ""),
    ("UHPT-UHMA-B350.json", "", ""),
    ("UHPT-UHMA-SF34.json", "", ""),
    ("UHSH-UHMM-B350.json", "", ""),
])
def test_detect_shutdown_phase_from_real_files(filename, expected_start, expected_end, shutdown_detector, context):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)

    assert result is not None, f"Shutdown not detected in {filename}"
    start, end = result

    expected_start_dt = parse_timestamp(expected_start)
    expected_end_dt = parse_timestamp(expected_end)

    assert start == expected_start_dt, f"Incorrect start for shutdown in {filename}"
    assert end == expected_end_dt, f"Incorrect end for shutdown in {filename}"
