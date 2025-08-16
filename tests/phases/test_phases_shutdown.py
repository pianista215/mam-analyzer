import json
import os
from datetime import datetime
import pytest

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.detectors.shutdown import ShutdownDetector
from mam_analyzer.utils.parsing import parse_timestamp

@pytest.fixture
def shutdown_detector():
    return ShutdownDetector()

@pytest.fixture
def context():
    return FlightDetectorContext()

def test_no_detect_shutdown_phase_synthetic(shutdown_detector, context):
    raw_events = [
        {"Timestamp": "2025-06-14T17:10:00.000000", "Changes": {"Latitude": "39,020", "Longitude": "2,000"}},
        {"Timestamp": "2025-06-14T17:12:00.000000", "Changes": {"Flaps": "0"}},
        {"Timestamp": "2025-06-14T17:13:00.000000", "Changes": {"Latitude": "39,005", "Longitude": "2,000"}},
        {"Timestamp": "2025-06-14T17:14:00.000000", "Changes": {"Squawk": "1234"}},
        {"Timestamp": "2025-06-14T17:15:00.000000", "Changes": {"Latitude": "39,000", "Longitude": "2,000"}},
    ]

    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)
    assert result is None

def test_detect_shutdown_full_event_single_engine(shutdown_detector, context):
    raw_events = [
        {
            "Timestamp": "2025-06-14T17:10:00.000000", 
            "Changes": {
                "Latitude": "39,070", 
                "Longitude": "2,080",
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
                "Engine 1": "On",
            }
        },
        {
            "Timestamp": "2025-06-14T17:11:00.000000", 
            "Changes": {
                "Latitude": "39,020", 
                "Longitude": "2,000",
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
            }
        },
        {"Timestamp": "2025-06-14T17:12:00.000000", "Changes": {"Flaps": "0"}},
        {"Timestamp": "2025-06-14T17:14:00.000000", "Changes": {"Squawk": "1234"}},
    ]

    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)
    assert result is not None
    start, end = result
    assert start == parse_timestamp("2025-06-14T17:11:00.000000")
    assert end == parse_timestamp("2025-06-14T17:14:00.000000") 

def test_detect_shutdown_full_event_multi_engine(shutdown_detector, context):
    raw_events = [
        {
            "Timestamp": "2025-06-14T17:10:00.000000", 
            "Changes": {
                "Latitude": "39,070", 
                "Longitude": "2,080",
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
                "Engine 1": "On",
                "Engine 2": "On",
            }
        },
        {
            "Timestamp": "2025-06-14T17:11:00.000000", 
            "Changes": {
                "Latitude": "39,020", 
                "Longitude": "2,000",
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
                "Engine 2": "Off",
            }
        },
        {"Timestamp": "2025-06-14T17:12:00.000000", "Changes": {"Flaps": "0"}},
        {"Timestamp": "2025-06-14T17:14:00.000000", "Changes": {"Squawk": "1234"}},
    ]

    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)
    assert result is not None
    start, end = result
    assert start == parse_timestamp("2025-06-14T17:11:00.000000")
    assert end == parse_timestamp("2025-06-14T17:14:00.000000")     

def test_detect_shutdown_changes_single_engine(shutdown_detector, context):
    raw_events = [
        {
            "Timestamp": "2025-06-14T17:09:00.000000", 
            "Changes": {
                "Latitude": "39,010", 
                "Longitude": "2,050",
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
                "Engine 1": "On",
            }
        },
        {
            "Timestamp": "2025-06-14T17:10:00.000000", 
            "Changes": {
                "Latitude": "39,070", 
                "Longitude": "2,080",
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
                "Engine 1": "On",
            }
        },
        {
            "Timestamp": "2025-06-14T17:11:00.000000", 
            "Changes": {
                "Engine 1": "Off",
            }
        },
        {"Timestamp": "2025-06-14T17:12:00.000000", "Changes": {"Flaps": "0"}},
        {"Timestamp": "2025-06-14T17:14:00.000000", "Changes": {"Squawk": "1234"}},
    ]

    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)
    assert result is not None
    start, end = result
    assert start == parse_timestamp("2025-06-14T17:10:00.000000")
    assert end == parse_timestamp("2025-06-14T17:14:00.000000") 

def test_detect_shutdown_changes_multi_engine(shutdown_detector, context):
    raw_events = [
        {
            "Timestamp": "2025-06-14T17:09:00.000000", 
            "Changes": {
                "Latitude": "39,010", 
                "Longitude": "2,050",
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
                "Engine 1": "On",
                "Engine 2": "On",
            }
        },
        {
            "Timestamp": "2025-06-14T17:10:00.000000", 
            "Changes": {
                "Latitude": "39,070", 
                "Longitude": "2,080",
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
                "Engine 1": "On",
                "Engine 2": "On",
            }
        },
        {
            "Timestamp": "2025-06-14T17:11:00.000000", 
            "Changes": {
                "Engine 1": "Off",
            }
        },
        {
            "Timestamp": "2025-06-14T17:12:00.000000", 
            "Changes": {
                "Engine 2": "Off",
            }
        },
        {"Timestamp": "2025-06-14T17:13:00.000000", "Changes": {"Flaps": "0"}},
        {"Timestamp": "2025-06-14T17:14:00.000000", "Changes": {"Squawk": "1234"}},
    ]

    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)
    assert result is not None
    start, end = result
    assert start == parse_timestamp("2025-06-14T17:10:00.000000")
    assert end == parse_timestamp("2025-06-14T17:14:00.000000")


def test_detect_engine_failure_landing_shutdown(shutdown_detector, context):
    raw_events = [
        {
            "Timestamp": "2025-06-14T17:09:00.000000", 
            "Changes": {
                "Latitude": "39,010", 
                "Longitude": "2,050",
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
                "Engine 1": "On",
                "Engine 2": "Off",
            }
        },
        {
            "Timestamp": "2025-06-14T17:10:00.000000", 
            "Changes": {
                "Latitude": "39,070", 
                "Longitude": "2,080",
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
                "Engine 1": "On",
                "Engine 2": "Off",
            }
        },
        {
            "Timestamp": "2025-06-14T17:11:00.000000", 
            "Changes": {
                "Engine 1": "Off",
            }
        },
        {"Timestamp": "2025-06-14T17:13:00.000000", "Changes": {"Flaps": "0"}},
        {"Timestamp": "2025-06-14T17:14:00.000000", "Changes": {"Squawk": "1234"}},
    ]

    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)
    assert result is not None
    start, end = result
    assert start == parse_timestamp("2025-06-14T17:10:00.000000")
    assert end == parse_timestamp("2025-06-14T17:14:00.000000") 

def test_detect_engine_shutdown_slow(shutdown_detector, context):
    raw_events = [
        {
            "Timestamp": "2025-06-14T17:05:00.000000", 
            "Changes": {
                "Latitude": "39,010", 
                "Longitude": "2,050",
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
                "Engine 1": "On",
                "Engine 2": "On",
            }
        },
        {
            "Timestamp": "2025-06-14T17:07:00.000000", 
            "Changes": {
                "Engine 1": "Off",
            }
        },
        {
            "Timestamp": "2025-06-14T17:10:00.000000", 
            "Changes": {
                "Latitude": "39,070", 
                "Longitude": "2,080",
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
                "Engine 2": "On",
            }
        },
        {
            "Timestamp": "2025-06-14T17:11:00.000000", 
            "Changes": {
                "Engine 2": "Off",
            }
        },
        {"Timestamp": "2025-06-14T17:13:00.000000", "Changes": {"Flaps": "0"}},
        {"Timestamp": "2025-06-14T17:14:00.000000", "Changes": {"Squawk": "1234"}},
    ]

    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)
    assert result is not None
    start, end = result
    assert start == parse_timestamp("2025-06-14T17:07:00.000000")
    assert end == parse_timestamp("2025-06-14T17:14:00.000000")                


@pytest.mark.parametrize("filename, expected_start, expected_end", [
    ("LEPA-LEPP-737.json", "2025-06-14T18:26:59.8779366", "2025-06-14T18:29:23.9003458"),
    ("LEPP-LEMG-737.json", "2025-06-15T01:11:26.9540678", "2025-06-15T01:15:06.9660548"),
    ("LPMA-Circuits-737.json", "None", "None"),
    ("UHMA-PAOM-B350.json", "2025-06-16T00:12:10.5865817", "2025-06-16T00:21:44.5809936"),
    ("UHPT-UHMA-B350.json", "2025-06-15T20:09:06.8168029", "2025-06-15T20:09:08.8279072"),
    ("UHPT-UHMA-SF34.json", "2025-06-05T15:10:25.2342953", "2025-06-05T15:11:27.2262993"),
    ("UHSH-UHMM-B350.json", "2025-05-17T19:44:49.2465901", "2025-05-17T19:46:07.2591295"),
])
def test_detect_shutdown_phase_from_real_files(filename, expected_start, expected_end, shutdown_detector, context):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]

    result = shutdown_detector.detect(events, None, None, context)

    if expected_start != 'None' and expected_end != 'None':
        assert result is not None, f"Shutdown not detected in {filename}"
        start, end = result

        expected_start_dt = parse_timestamp(expected_start)
        expected_end_dt = parse_timestamp(expected_end)

        assert start == expected_start_dt, f"Incorrect start for shutdown in {filename}"
        assert end == expected_end_dt, f"Incorrect end for shutdown in {filename}"

    else:
        assert result is None, f"Shutdown shouldn't been detected in {filename}"
