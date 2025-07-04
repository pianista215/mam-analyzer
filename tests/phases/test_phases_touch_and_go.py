import pytest
from datetime import datetime, timedelta
from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.phases.touch_go import TouchAndGoDetector
from mam_analyzer.models.flight_events import FlightEvent

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
