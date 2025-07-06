from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.cruise import CruiseDetector
from mam_analyzer.utils.parsing import parse_timestamp


def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)

@pytest.fixture
def detector():
    return CruiseDetector()

@pytest.fixture
def context():
    return FlightDetectorContext()

def test_no_cruise_due_to_low_agl_altitude(detector, context):
    base = datetime(2025, 7, 5, 10, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=10)
    events = [
        make_event(base + timedelta(seconds=i * 30), Altitude=2000, AGLAltitude=1000)
        for i in range(20)
    ]
    result = detector.detect(events, from_time, to_time, context)
    assert result is None    


def test_cruise_detected_above_10000_ft_agl(detector, context):
    base = datetime(2025, 7, 5, 11, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=10)
    events = list()

    for i in range(10):
        seconds = base + timedelta(seconds=i * 60)
        if i < 2:
            events.append(
                make_event(seconds, Altitude=21000, AGLAltitude=19000)
            )
        elif i < 5:
            events.append(
                make_event(seconds, Altitude = 25000, AGLAltitude = 23000) # start
            ) 
        elif i < 7:
            events.append(
                make_event(seconds, Altitude = 27000, AGLAltitude = 25000)
            )
        else:
            events.append(
                make_event(seconds, Altitude = 24000, AGLAltitude = 22000) # end
            )
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(minutes = 2)
    assert end == base + timedelta(minutes=10)


def test_cruise_detected_above_7000_ft_agl(detector, context):
    base = datetime(2025, 7, 5, 11, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=20)
    events = list()

    for i in range(20):
        seconds = base + timedelta(seconds=i * 60)
        if i < 2:
            events.append(
                make_event(seconds, Altitude=5000, AGLAltitude=4000)
            )
        elif i < 5:
            events.append(
                make_event(seconds, Altitude = 8000, AGLAltitude = 7000) # start
            ) 
        elif i < 14:
            events.append(
                make_event(seconds, Altitude = 9000, AGLAltitude = 8000) # end
            )
        else:
            events.append(
                make_event(seconds, Altitude = 5000, AGLAltitude = 4000) 
            )
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(minutes = 2)
    assert end == base + timedelta(minutes=13)

def test_cruise_detected_above_3000_ft_agl(detector, context):
    base = datetime(2025, 7, 5, 11, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=20)
    events = list()

    for i in range(20):
        seconds = base + timedelta(seconds=i * 60)
        if i < 2:
            events.append(
                make_event(seconds, Altitude=4500, AGLAltitude=2000) # start
            )
        elif i < 5:
            events.append(
                make_event(seconds, Altitude = 5500, AGLAltitude = 3500)
            ) 
        elif i < 14:
            events.append(
                make_event(seconds, Altitude = 4500, AGLAltitude = 2000)
            )
        else:
            events.append(
                make_event(seconds, Altitude = 5500, AGLAltitude = 3500) #end
            )
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(minutes = 0)
    assert end == base + timedelta(minutes=20) 