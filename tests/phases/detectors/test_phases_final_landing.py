import json
import os
from datetime import datetime, timedelta
import pytest

from mam_analyzer.models.flight_context import AirportContext, FlightContext, Runway, RunwayEnd
from mam_analyzer.phases.detectors.final_landing import FinalLandingDetector
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.utils.parsing import parse_timestamp
from runway_data import make_flight_context

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


# === Tests with runway context ===

def _make_runway(lat1, lon1, heading1, lat2, lon2, heading2, designator1, designator2, width_m=45, length_m=3000):
    return Runway(
        designators=f"{designator1}/{designator2}",
        width_m=width_m,
        length_m=length_m,
        ends=[
            RunwayEnd(designator=designator1, latitude=lat1, longitude=lon1,
                      true_heading_deg=heading1, displaced_threshold_m=0, stopway_m=0),
            RunwayEnd(designator=designator2, latitude=lat2, longitude=lon2,
                      true_heading_deg=heading2, displaced_threshold_m=0, stopway_m=0),
        ],
    )


def _make_context_with_landing_runway(runway):
    return FlightContext(
        departure=AirportContext(icao="ORIG"),
        destination=AirportContext(icao="DEST"),
        landing=AirportContext(icao="DEST", runways=[runway]),
    )


def test_landing_with_context_uses_runway_polygon(detector):
    """When context with runway is provided, landing end is determined by runway polygon."""
    base = datetime(2025, 6, 23, 10, 0, 0)

    # Runway roughly heading 90 (east), from (40.0, -3.010) to (40.0, -2.980)
    rwy = _make_runway(
        lat1=40.0, lon1=-3.010, heading1=90,
        lat2=40.0, lon2=-2.980, heading2=270,
        designator1="09", designator2="27",
        width_m=45, length_m=2600,
    )
    ctx = _make_context_with_landing_runway(rwy)

    events = [
        make_full_event(base + timedelta(seconds=0), Heading=90, onGround=False),
        # Touchdown on the runway
        make_full_event(base + timedelta(seconds=10), Heading=90, LandingVSFpm=-300, onGround=True,
                        Latitude=40.0, Longitude=-3.005),
        # Still on runway
        make_event(base + timedelta(seconds=15), Heading=90, Latitude=40.0, Longitude=-2.998),
        # Still on runway
        make_event(base + timedelta(seconds=20), Heading=90, Latitude=40.0, Longitude=-2.985),
        # Off the runway
        make_event(base + timedelta(seconds=25), Heading=90, Latitude=40.001, Longitude=-2.970),
        make_event(base + timedelta(seconds=30), Heading=120),
    ]

    start, end = detector.detect(events, None, None, context=ctx)
    assert start == base + timedelta(seconds=10)
    # Last event inside runway is at seconds=20, first outside is at seconds=25
    assert end == base + timedelta(seconds=20)


def test_landing_without_context_uses_heading_fallback(detector):
    """Without context, the heading-based fallback is used."""
    base = datetime(2025, 6, 23, 10, 0, 0)
    events = [
        make_full_event(base + timedelta(seconds=0), Heading=90, onGround=False),
        make_full_event(base + timedelta(seconds=10), Heading=90, LandingVSFpm=-300, onGround=True),
        make_event(base + timedelta(seconds=15), Heading=92),
        make_event(base + timedelta(seconds=20), Heading=130),
        make_event(base + timedelta(seconds=25), Heading=140),
    ]
    start, end = detector.detect(events, None, None, context=None)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=15)


def test_landing_with_context_no_matching_runway_falls_back(detector):
    """If context has runways but none match heading, heading fallback is used."""
    base = datetime(2025, 6, 23, 10, 0, 0)

    # Runway heading 180/360 but landing heading is 90
    rwy = _make_runway(
        lat1=40.0, lon1=-3.0, heading1=180,
        lat2=39.97, lon2=-3.0, heading2=360,
        designator1="18", designator2="36",
    )
    ctx = _make_context_with_landing_runway(rwy)

    events = [
        make_full_event(base + timedelta(seconds=0), Heading=90, onGround=False),
        make_full_event(base + timedelta(seconds=10), Heading=90, LandingVSFpm=-300, onGround=True,
                        Latitude=40.0, Longitude=-3.0),
        make_event(base + timedelta(seconds=15), Heading=92),
        make_event(base + timedelta(seconds=20), Heading=130),
    ]
    start, end = detector.detect(events, None, None, context=ctx)
    assert start == base + timedelta(seconds=10)
    # Falls back to heading logic
    assert end == base + timedelta(seconds=15)


# === Real file tests: context WITHOUT runways (same expected values) ===

@pytest.mark.parametrize("filename, departure, landing, expected_start, expected_end", [
    ("LEPA-LEPP-737.json", "LEPA", "LEPP", "2025-06-14T18:22:03.8839814", "2025-06-14T18:22:43.8757681"),
    ("LEPP-LEMG-737.json", "LEPP", "LEMG", "2025-06-15T01:08:58.9593068", "2025-06-15T01:09:24.96811"),
    ("LPMA-Circuits-737.json", "LPMA", "LPMA", "2025-06-02T22:13:43.7386248", "2025-06-02T22:14:05.7377146"),
    ("UHMA-PAOM-B350.json", "UHMA", "PAOM", "2025-06-16T00:07:26.5753238", "2025-06-16T00:07:44.5761254"),
    ("UHPT-UHMA-B350.json", "UHPT", "UHMA", "2025-06-15T20:01:00.8191063", "2025-06-15T20:03:02.8108667"),
    ("UHPT-UHMA-SF34.json", "UHPT", "UHMA", "2025-06-05T15:05:21.2266523", "2025-06-05T15:07:23.2129155"),
    ("UHSH-UHMM-B350.json", "UHSH", "UHMM", "2025-05-17T19:41:01.243375", "2025-05-17T19:42:55.2530305"),
    ("PAOM-PANC-B350-fromtaxi.json", "PAOM", "PANC", "2025-06-23T00:15:48.5520445", "2025-06-23T00:16:16.5747404"),
    ("LEBB-touchgoLEXJ-LEAS.json", "LEBB", "LEAS", "2025-07-04T23:44:13.3164862", "2025-07-04T23:44:13.3164862"),
])
def test_landing_with_context_no_runways(filename, departure, landing, expected_start, expected_end, detector):
    """Context without runways should produce identical results to no context."""
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    events = [FlightEvent.from_json(e) for e in data["Events"]]
    ctx = make_flight_context(departure, landing, with_runways=False)
    result = detector.detect(events, None, None, context=ctx)

    if expected_start != 'None' and expected_end != 'None':
        assert result is not None, f"Final landing not detected in {filename}"
        start, end = result
        assert start == parse_timestamp(expected_start), f"Incorrect start in {filename}"
        assert end == parse_timestamp(expected_end), f"Incorrect end in {filename}"
    else:
        assert result is None


# === Real file tests: context WITH runways (end may differ due to polygon detection) ===

@pytest.mark.parametrize("filename, departure, landing, expected_start, expected_end", [
    ("LEPA-LEPP-737.json", "LEPA", "LEPP", "2025-06-14T18:22:03.8839814", "2025-06-14T18:22:43.8757681"),
    ("LEPP-LEMG-737.json", "LEPP", "LEMG", "2025-06-15T01:08:58.9593068", "2025-06-15T01:09:24.96811"),
    ("LPMA-Circuits-737.json", "LPMA", "LPMA", "2025-06-02T22:13:43.7386248", "2025-06-02T22:14:05.7377146"),
    ("UHMA-PAOM-B350.json", "UHMA", "PAOM", "2025-06-16T00:07:26.5753238", "2025-06-16T00:07:44.5761254"),
    ("UHPT-UHMA-B350.json", "UHPT", "UHMA", "2025-06-15T20:01:00.8191063", "2025-06-15T20:03:02.8108667"),
    ("UHPT-UHMA-SF34.json", "UHPT", "UHMA", "2025-06-05T15:05:21.2266523", "2025-06-05T15:07:23.2129155"),
    ("UHSH-UHMM-B350.json", "UHSH", "UHMM", "2025-05-17T19:41:01.243375", "2025-05-17T19:42:55.2530305"),
    ("PAOM-PANC-B350-fromtaxi.json", "PAOM", "PANC", "2025-06-23T00:15:48.5520445", "2025-06-23T00:16:16.5747404"),
    ("LEBB-touchgoLEXJ-LEAS.json", "LEBB", "LEAS", "2025-07-04T23:44:13.3164862", "2025-07-04T23:44:13.3164862"),
])
def test_landing_with_context_and_runways(filename, departure, landing, expected_start, expected_end, detector):
    """Context with real runways - end may differ from heading-based detection."""
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    events = [FlightEvent.from_json(e) for e in data["Events"]]
    ctx = make_flight_context(departure, landing, with_runways=True)
    result = detector.detect(events, None, None, context=ctx)

    if expected_start != 'None' and expected_end != 'None':
        assert result is not None, f"Final landing not detected in {filename}"
        start, end = result
        assert start == parse_timestamp(expected_start), f"Incorrect start in {filename}"
        assert end == parse_timestamp(expected_end), f"Incorrect end in {filename}"
    else:
        assert result is None
