import json
import os
from datetime import datetime
import pytest

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.startup import StartupDetector
from mam_analyzer.utils.parsing import parse_timestamp

@pytest.fixture
def startup_detector():
    return StartupDetector()

@pytest.fixture
def context():
    return FlightDetectorContext()

def test_detect_engine_start_phase_synthetic_single(startup_detector, context):
    raw_events = [
        {
            "Timestamp": "2025-06-14T17:00:00.1234567", 
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
            },
        },
        {"Timestamp": "2025-06-14T17:01:00.23478", "Changes": {"Squawk": "1234"}},
        {"Timestamp": "2025-06-14T17:02:00.3234679", "Changes": {"Flaps": "49"}},
        {"Timestamp": "2025-06-14T17:03:00.3234679", "Changes": {"Engine 1": "On"}},
        {
            "Timestamp": "2025-06-14T17:04:00.3234679", 
            "Changes": {
                "Latitude": "39,072", 
                "Longitude": "2,081",
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
                "Engine 1": "On"
            }
        },
        {
            "Timestamp": "2025-06-14T17:05:00.3234679", 
            "Changes": {
                "Latitude": "39,079",
                "Longitude": "2,081",
            }
        },
    ]

    events = [FlightEvent.from_json(e) for e in raw_events]

    result = startup_detector.detect(events, None, None, context)
    assert result is not None
    start, end = result
    assert start == parse_timestamp("2025-06-14T17:00:00.1234567")
    assert end == parse_timestamp("2025-06-14T17:04:00.3234679")

@pytest.mark.parametrize("filename, expected_start, expected_end", [
    ("LEPA-LEPP-737.json", "2025-06-14T17:03:35.5975269", "2025-06-14T17:10:41.9052048"),
    ("LEPP-LEMG-737.json", "2025-06-14T23:26:04.9623655", "2025-06-14T23:46:28.9605062"),
    ("LPMA-Circuits-737.json", "2025-06-02T21:17:25.7327066", "2025-06-02T21:43:03.7395263"),
    ("UHMA-PAOM-B350.json", "2025-06-15T21:57:38.5719388", "2025-06-15T22:16:58.5783802"),
    ("UHPT-UHMA-B350.json", "2025-06-15T17:58:20.8040915", "2025-06-15T18:12:32.8254948"),
    ("UHPT-UHMA-SF34.json", "2025-06-05T12:59:29.2149344", "2025-06-05T13:03:33.2361648"),
    ("UHSH-UHMM-B350.json", "2025-05-17T17:35:51.2435736", "2025-05-17T17:52:11.2488295"),
    ("PAOM-PANC-B350-fromtaxi.json", "None", "None"),
])    
def test_detect_engine_start_phase_from_real_files(filename, expected_start, expected_end, startup_detector, context):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = startup_detector.detect(events, None, None, context)

    if expected_start != 'None' and expected_end != 'None':
        assert result is not None, f"Startup not detected in {filename}"
        start, end = result

        expected_start_dt = parse_timestamp(expected_start)
        expected_end_dt = parse_timestamp(expected_end)

        assert start == expected_start_dt, f"Incorrect start for startup in {filename}"
        assert end == expected_end_dt, f"Incorrect end for startup in {filename}"

    else:
        assert result is None, f"Startup shouldn't been detected in {filename}"