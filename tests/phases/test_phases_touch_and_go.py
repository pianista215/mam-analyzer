from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.touch_go import TouchAndGoDetector
from mam_analyzer.utils.parsing import parse_timestamp


def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)

@pytest.fixture
def detector():
    return TouchAndGoDetector()

@pytest.fixture
def context():
    return FlightDetectorContext()

def test_touch_and_go_normal_flaps(detector, context):
    base = datetime(2025, 7, 4, 10, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=5)
    events = [
        make_event(base + timedelta(seconds=0), onGround=False),
        make_event(base + timedelta(seconds=10), onGround=True, Flaps=5),
        make_event(base + timedelta(seconds=15), onGround=False, Flaps=5),
        make_event(base + timedelta(seconds=25), Flaps=2),
        make_event(base + timedelta(seconds=30), Flaps=0),  # Should end here
    ]
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=30)

def test_no_touch_and_go_returns_none(detector, context):
    base = datetime(2025, 7, 4, 11, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=5)
    events = [
        make_event(base + timedelta(seconds=0), onGround=False),
        make_event(base + timedelta(seconds=30), Flaps=0),
    ]
    result = detector.detect(events, from_time, to_time, context)
    assert result is None

def test_touch_and_go_with_one_bounce(detector, context):
    base = datetime(2025, 7, 4, 12, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=5)
    events = [
        make_event(base + timedelta(seconds=0), onGround=False),
        make_event(base + timedelta(seconds=10), onGround=True, Flaps=10),  # initial touch
        make_event(base + timedelta(seconds=12), onGround=False, Flaps=10),  # airborne
        make_event(base + timedelta(seconds=18), onGround=True, Flaps=10),  # bounce
        make_event(base + timedelta(seconds=19), onGround=False, Flaps=10),
        make_event(base + timedelta(seconds=30), Flaps=0),
    ]
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=30)

def test_touch_and_go_with_two_bounces(detector, context):
    base = datetime(2025, 7, 4, 13, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=5)
    events = [
        make_event(base + timedelta(seconds=0), onGround=False),
        make_event(base + timedelta(seconds=10), onGround=True, Flaps=10),
        make_event(base + timedelta(seconds=11), onGround=False, Flaps=10),
        make_event(base + timedelta(seconds=17), onGround=True, Flaps=10),  # bounce 1
        make_event(base + timedelta(seconds=18), onGround=False, Flaps=10),
        make_event(base + timedelta(seconds=22), onGround=True, Flaps=10),  # bounce 2
        make_event(base + timedelta(seconds=23), onGround=False, Flaps=10),
        make_event(base + timedelta(seconds=35), Flaps=0),
    ]
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=35)

def test_touch_and_go_with_flaps_0_and_gear_up(detector, context):
    base = datetime(2025, 7, 4, 14, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=5)
    events = [
        make_event(base + timedelta(seconds=0), onGround=False),
        make_event(base + timedelta(seconds=10), onGround=True, Flaps=0, Gear="Down"),
        make_event(base + timedelta(seconds=15), onGround=False, Flaps=0, Gear="Down"),
        make_event(base + timedelta(seconds=25), Gear="Up"),
    ]
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=25)

def test_touch_and_go_timeout_1_minute(detector, context):
    base = datetime(2025, 7, 4, 15, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=5)
    events = [
        make_event(base + timedelta(seconds=0), onGround=False),
        make_event(base + timedelta(seconds=10), onGround=True, Flaps=0, Gear="Down"),
        make_event(base + timedelta(seconds=15), onGround=False, Flaps=0, Gear="Down"),
        make_event(base + timedelta(seconds=30)),
        make_event(base + timedelta(seconds=75)),  # 60s after airborne
    ]
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(seconds=10)
    assert end == base + timedelta(seconds=75)

#Ensure always that from and to correspond with takeoff & final_landing tests
@pytest.mark.parametrize(
    "filename, from_time, to_time, expected_start, expected_end", [
    (
        "LEPA-LEPP-737.json", 
        "2025-06-14T17:19:23.8899645", 
        "2025-06-14T18:22:03.8839814", 
        "None", 
        "None"
    ),
    (
        "LEPP-LEMG-737.json", 
        "2025-06-14T23:51:02.9812455", 
        "2025-06-15T01:08:58.9593068", 
        "None", 
        "None"
    ),
    (
        "LPMA-Circuits-737.json", 
        "2025-06-02T21:49:51.7385484", 
        "2025-06-02T22:13:43.7386248", 
        "2025-06-02T22:04:09.7386262", 
        "2025-06-02T22:05:15.7409833"
    ),
    (
        "UHMA-PAOM-B350.json", 
        "2025-06-15T22:20:50.5779508", 
        "2025-06-16T00:07:26.5753238", 
        "None", 
        "None"
    ),
    (
        "UHPT-UHMA-B350.json", 
        "2025-06-15T18:18:16.828107", 
        "2025-06-15T20:01:00.8191063", 
        "None", 
        "None"
    ),
    (
        "UHPT-UHMA-SF34.json", 
        "2025-06-05T13:09:09.2296981", 
        "2025-06-05T15:05:21.2266523", 
        "None", 
        "None"
    ),
    (
        "UHSH-UHMM-B350.json", 
        "2025-05-17T17:57:09.2445871", 
        "2025-05-17T19:41:01.243375", 
        "None", 
        "None"
    ),
    (
        "PAOM-PANC-B350-fromtaxi.json", 
        "2025-06-22T22:26:42.5590209", 
        "2025-06-23T00:15:48.5520445", 
        "None", 
        "None"
    ),
])
def test_landing_detects_from_real_files(
    filename, 
    from_time, 
    to_time, 
    expected_start, 
    expected_end, 
    detector, 
    context
):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = detector.detect(events, parse_timestamp(from_time), parse_timestamp(to_time), context)

    if expected_start != 'None' and expected_end != 'None':
        assert result is not None, f"Touch & go not detected in {filename}"
        start, end = result

        expected_start_dt = parse_timestamp(expected_start)
        expected_end_dt = parse_timestamp(expected_end)

        assert start == expected_start_dt, f"Incorrect start for touch&go in {filename}"
        assert end == expected_end_dt, f"Incorrect end for touch&go in {filename}"

    else:
        assert result is None, f"Touch&go shouldn't been detected in {filename}"    
