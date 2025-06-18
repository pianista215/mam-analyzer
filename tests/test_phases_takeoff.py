import json
import os
from datetime import datetime, timedelta
import pytest

from mam_analyzer.phases import detect_takeoff_phase

def make_event(timestamp, **changes):
    return {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }

def test_takeoff_with_flaps_then_flaps_to_zero():
    base = datetime(2025, 6, 17, 10, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), onGround="True", Heading="40", Flaps="5"),
        make_event(base + timedelta(seconds=5), onGround="True", Heading="50"), # start
        make_event(base + timedelta(seconds=10), onGround="True", Heading="51"),
        make_event(base + timedelta(seconds=20), onGround="False", Heading="52"),
        make_event(base + timedelta(seconds=30), Flaps="2"),
        make_event(base + timedelta(seconds=40), Flaps="0"),  # end
    ]
    start, end = detect_takeoff_phase(events)
    assert start == base + timedelta(seconds=5)
    assert end == base + timedelta(seconds=40)


def test_takeoff_with_flaps_zero_then_gear_up():
    base = datetime(2025, 6, 17, 11, 0, 0)
    events = [
    	make_event(base + timedelta(seconds=0), onGround="True", Heading="70", Flaps="0"),
        make_event(base + timedelta(seconds=5), onGround="True", Heading="90"),
        make_event(base + timedelta(seconds=10), onGround="True", Heading="120"), # start
        make_event(base + timedelta(seconds=15), onGround="False", Heading="122"),
        make_event(base + timedelta(seconds=20), Heading="125"),
        make_event(base + timedelta(seconds=25), Gear="Up"),  # end
    ]
    start, end = detect_takeoff_phase(events)
    assert start == base + timedelta(seconds=5)
    assert end == base + timedelta(seconds=25)


def test_takeoff_with_no_flaps_or_gear_change_fallback_to_1min():
    base = datetime(2025, 6, 17, 12, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), onGround="True", Heading="200", Flaps="0"), #start
        make_event(base + timedelta(seconds=10), onGround="False", Heading="200"), 
        make_event(base + timedelta(seconds=30), Heading="205"),
        make_event(base + timedelta(seconds=61), Heading="210"),  # end
    ]
    start, end = detect_takeoff_phase(events)
    assert start == base + timedelta(seconds=0)
    assert end == base + timedelta(seconds=61)  # airborne + 1 min


def test_takeoff_with_heading_change_aborts_carrera():
    base = datetime(2025, 6, 17, 13, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), onGround="True", Heading="10", Flaps="30"),
        make_event(base + timedelta(seconds=5), onGround="True", Heading="90"),  # start
        make_event(base + timedelta(seconds=10), onGround="False", Heading="90", Flaps="10"),
        make_event(base + timedelta(seconds=20), Flaps="0"),  # end
    ]
    start, end = detect_takeoff_phase(events)
    assert start == base + timedelta(seconds=5)
    assert end == base + timedelta(seconds=20)


def test_takeoff_no_onGround_false_returns_none():
    base = datetime(2025, 6, 17, 14, 0, 0)
    events = [
        make_event(base + timedelta(seconds=0), onGround="True", Heading="250"),
        make_event(base + timedelta(seconds=5), Heading="250"),
        make_event(base + timedelta(seconds=10), Flaps="5"),
    ]
    result = detect_takeoff_phase(events)
    assert result is None    