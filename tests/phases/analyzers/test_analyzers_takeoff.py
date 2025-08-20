from datetime import datetime, timedelta
import pytest

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.takeoff import TakeoffAnalyzer
from mam_analyzer.utils.units import haversine


def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)


@pytest.fixture
def analyzer():
    return TakeoffAnalyzer()


def test_basic_takeoff_distance_and_speed(analyzer):
    base = datetime(2025, 7, 7, 9, 0, 0)
    events = []

    # First event
    run_start = make_event(base, Latitude=40.0, Longitude=-3.0, onGround=True, IASKnots=10)
    events.append(run_start)

    # On the runway
    for i in range(1, 4):
        ts = base + timedelta(seconds=2 * i)
        events.append(make_event(ts, Latitude=40.0, Longitude=-3.0 - 0.001 * i, onGround=True, IASKnots=50 + 10 * i))

    # Airborne: onGround=False + IAS
    airborne = make_event(base + timedelta(seconds=10), Latitude=40.0, Longitude=-3.005, onGround=False, IASKnots=135)
    events.append(airborne)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

    expected_distance = round(haversine(40.0, -3.0, 40.0, -3.005))
    assert result[0] == ("TakeoffBounces", [])
    assert result[1] == ("TakeoffGroundDistance", expected_distance)
    assert result[2] == ("TakeoffSpeed", 135)


def test_takeoff_with_bounces_resets_flags_but_keeps_run_start(analyzer):
    base = datetime(2025, 7, 7, 10, 0, 0)
    events = []

    # Takeoff start
    events.append(make_event(base, Latitude=41.0, Longitude=-3.0, onGround=True, IASKnots=20))

    # On the runway
    events.append(make_event(base + timedelta(seconds=2), Latitude=41.0, Longitude=-3.001, onGround=True, IASKnots=60))

    # Bounce 1
    events.append(make_event(base + timedelta(seconds=3), LandingVSFpm=-120, onGround=True))

    # Continue roll
    events.append(make_event(base + timedelta(seconds=5), Latitude=41.0, Longitude=-3.003, onGround=True, IASKnots=90))

    # Bounce 2
    events.append(make_event(base + timedelta(seconds=6), LandingVSFpm=-180, onGround=True))

    # Finally airborne (onGround=False) + IAS
    airborne = make_event(base + timedelta(seconds=9), Latitude=41.0, Longitude=-3.006, onGround=False, IASKnots=150)
    events.append(airborne)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

    expected_distance = round(haversine(41.0, -3.0, 41.0, -3.006))
    assert result[0] == ("TakeoffBounces", [-120, -180])
    assert result[1] == ("TakeoffGroundDistance", expected_distance)
    assert result[2] == ("TakeoffSpeed", 150)


def test_no_airborne_raises(analyzer):
    base = datetime(2025, 7, 7, 11, 0, 0)
    events = []

    # Never onGround=False
    events.append(make_event(base, Latitude=42.0, Longitude=-4.0, onGround=True, IASKnots=10))
    for i in range(1, 6):
        ts = base + timedelta(seconds=2 * i)
        events.append(make_event(ts, Latitude=42.0, Longitude=-4.0 - 0.001 * i, onGround=True, IASKnots=40 + 10 * i))

    with pytest.raises(RuntimeError, match="Can't get meters and speed for takeoff phase"):
        analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)


def test_airborne_without_ias_raises(analyzer):
    base = datetime(2025, 7, 7, 12, 0, 0)
    events = []

    # Start
    events.append(make_event(base, Latitude=43.0, Longitude=-5.0, onGround=True, IASKnots=15))
    events.append(make_event(base + timedelta(seconds=2), Latitude=43.0, Longitude=-5.002, onGround=True, IASKnots=70))

    # Airborne without IAS
    events.append(make_event(base + timedelta(seconds=6), Latitude=43.0, Longitude=-5.004, onGround=False))

    with pytest.raises(RuntimeError, match="Event marking airborne must include IAS"):
        analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)


def test_run_start_is_first_location_even_if_initial_events_have_no_location(analyzer):
    base = datetime(2025, 7, 7, 13, 0, 0)
    events = []

    # First events without location (shouldn't affect)
    events.append(make_event(base, onGround=True, IASKnots=5))
    events.append(make_event(base + timedelta(seconds=1), onGround=True, IASKnots=15))

    # First event with location -> start of the run
    run_start = make_event(base + timedelta(seconds=2), Latitude=44.0, Longitude=-6.0, onGround=True, IASKnots=25)
    events.append(run_start)

    # On the runway
    events.append(make_event(base + timedelta(seconds=4), Latitude=44.0, Longitude=-6.003, onGround=True, IASKnots=80))

    # Airborne + IAS
    airborne = make_event(base + timedelta(seconds=7), Latitude=44.0, Longitude=-6.006, onGround=False, IASKnots=140)
    events.append(airborne)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

    expected_distance = round(haversine(44.0, -6.0, 44.0, -6.006))
    assert result[1] == ("TakeoffGroundDistance", expected_distance)
    assert result[2] == ("TakeoffSpeed", 140)


def test_first_location_is_sticky_even_if_next_locations_change(analyzer):
    base = datetime(2025, 7, 7, 14, 0, 0)
    events = []

    # Run start
    run_start = make_event(base, Latitude=45.0, Longitude=-7.000, onGround=True, IASKnots=20)
    events.append(run_start)

    # Other events with diff locations (shouldn't affect)
    events.append(make_event(base + timedelta(seconds=2), Latitude=45.001, Longitude=-7.001, onGround=True, IASKnots=60))
    events.append(make_event(base + timedelta(seconds=4), Latitude=45.002, Longitude=-7.002, onGround=True, IASKnots=90))

    # Airborne final
    airborne = make_event(base + timedelta(seconds=7), Latitude=45.003, Longitude=-7.004, onGround=False, IASKnots=145)
    events.append(airborne)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

    expected_distance = round(haversine(45.0, -7.000, 45.003, -7.004))
    assert result[1] == ("TakeoffGroundDistance", expected_distance)
    assert result[2] == ("TakeoffSpeed", 145)
