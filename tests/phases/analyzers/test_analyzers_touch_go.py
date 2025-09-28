from datetime import datetime, timedelta
import json
import os
import pytest


from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.touch_go import TouchAndGoAnalyzer
from mam_analyzer.utils.parsing import parse_timestamp
from mam_analyzer.utils.units import haversine


def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)


@pytest.fixture
def analyzer():
    return TouchAndGoAnalyzer()


def test_basic_touch_and_go(analyzer):
    base = datetime(2025, 7, 6, 17, 0, 0)
    events = []

    # First touchdown
    touchdown = make_event(base, LandingVSFpm=-300, IASKnots=110, Latitude=40.0, Longitude=-3.0, onGround=True)
    events.append(touchdown)

    # Rollout for a while
    for i in range(3):
        ts = base + timedelta(seconds=3 * (i + 1))
        events.append(make_event(ts, IASKnots=100 - i*5, Latitude=40.0, Longitude=-3.0 - 0.001*(i+1), onGround=True))

    # Airborne again
    airborne = make_event(base + timedelta(seconds=15), IASKnots=120, Latitude=40.0, Longitude=-3.005, onGround=False)
    events.append(airborne)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

    expected_distance = round(haversine(40.0, -3.0, 40.0, -3.005))
    assert result.phase_metrics["TouchGoVSFpm"] == -300
    assert result.phase_metrics["TouchGoBounces"] == []
    assert result.phase_metrics["TouchGoGroundDistance"] == expected_distance


def test_touch_and_go_with_bounces(analyzer):
    base = datetime(2025, 7, 6, 17, 0, 0)
    events = []

    # Touchdown
    touchdown = make_event(base, LandingVSFpm=-250, IASKnots=95, Latitude=44.0, Longitude=-3.0, onGround="True")
    events.append(touchdown)

    # First airborne before touchdown
    airborne1 = make_event(base + timedelta(seconds=2), IASKnots=94, Latitude=44.0, Longitude=-3.0005, onGround="False")
    events.append(airborne1)

    # Bounce 1
    bounce1 = make_event(base + timedelta(seconds=3), LandingVSFpm=-180, IASKnots=93, Latitude=44.0, Longitude=-3.001, onGround="True")
    events.append(bounce1)

    # Airborne until bounce
    airborne2 = make_event(base + timedelta(seconds=4), IASKnots=92, Latitude=44.0, Longitude=-3.0015, onGround="False")
    events.append(airborne2)

    # Bounce 2
    bounce2 = make_event(base + timedelta(seconds=5), LandingVSFpm=-220, IASKnots=91, Latitude=44.0, Longitude=-3.002, onGround="True")
    events.append(bounce2)

    # Finally taking off (onGround=False y speed and altitude increase)
    takeoff = make_event(base + timedelta(seconds=10), IASKnots=100, Latitude=44.0, Longitude=-3.005, onGround="False")
    events.append(takeoff)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

    expected_distance = round(haversine(44.0, -3.0, 44.0, -3.005))

    assert result.phase_metrics["TouchGoVSFpm"] == -250
    assert result.phase_metrics["TouchGoBounces"] == [-180, -220]
    assert result.phase_metrics["TouchGoGroundDistance"] == expected_distance



def test_no_touchdown_raises(analyzer):
    base = datetime(2025, 7, 6, 15, 0, 0)
    events = [make_event(base + timedelta(seconds=i*5), IASKnots=100) for i in range(5)]

    with pytest.raises(RuntimeError, match="Can't find touchdown from touch & go phase"):
        analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

@pytest.mark.parametrize(
    "filename, touch_go_start, touch_go_end, touch_go_vs, bounces_str, touch_ground_distance", [
    (
        "LPMA-Circuits-737.json", 
        "2025-06-02T22:04:09.7386262", 
        "2025-06-02T22:05:15.7409833", 
        "-55", 
        "",
        "354"
    ),
    (
        "LEBB-touchgoLEXJ-LEAS.json", 
        "2025-07-04T23:07:23.315419", 
        "2025-07-04T23:08:17.3078436", 
        "-193", 
        "",
        "418"
    ),
])
def test_touch_go_analyzer_from_real_files(filename, touch_go_start, touch_go_end, touch_go_vs, bounces_str, touch_ground_distance, analyzer):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = analyzer.analyze(events, parse_timestamp(touch_go_start), parse_timestamp(touch_go_end))

    expected_bounces = bounces = [int(x) for x in bounces_str.split("|")] if bounces_str else []    

    assert result.phase_metrics["TouchGoVSFpm"] == int(touch_go_vs)
    assert result.phase_metrics["TouchGoBounces"] == expected_bounces
    assert result.phase_metrics["TouchGoGroundDistance"] == int(touch_ground_distance)
