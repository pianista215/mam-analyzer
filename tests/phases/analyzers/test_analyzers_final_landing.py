from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.final_landing import FinalLandingAnalyzer
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
    return FinalLandingAnalyzer()


def test_basic_landing_and_brake(analyzer):
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = []

    # Touchdown
    touchdown = make_event(base, LandingVSFpm=-250, IASKnots=120, Latitude=40.0, Longitude=-3.0)
    events.append(touchdown)

    # Rollout events (travel in ground to -3.01)
    for i in range(5):
        ts = base + timedelta(seconds=5 * (i + 1))
        events.append(make_event(ts, IASKnots=100 - i*10, Latitude=40.0, Longitude=-3.0 + 0.001*(i+1)))

    # Event below 40 knots (braking finished)
    final = make_event(base + timedelta(seconds=40), IASKnots=30, Latitude=40.0, Longitude=-3.01)
    events.append(final)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

    expected_distance = round(haversine(40.0, -3.0, 40.0, -3.01))
    assert result.phase_metrics["LandingVSFpm"] == -250
    assert result.phase_metrics["LandingBounces"] == []
    assert result.phase_metrics["BrakeDistance"] == expected_distance


def test_landing_with_bounces(analyzer):
    base = datetime(2025, 7, 6, 13, 0, 0)
    events = []

    touchdown = make_event(base, LandingVSFpm=-300, IASKnots=110, Latitude=41.0, Longitude=-3.0)
    events.append(touchdown)

    # Bounce 1
    bounce1 = make_event(base + timedelta(seconds=3), LandingVSFpm=-180, IASKnots=100, Latitude=41.0, Longitude=-3.001)
    events.append(bounce1)

    # Bounce 2
    bounce2 = make_event(base + timedelta(seconds=6), LandingVSFpm=-220, IASKnots=90, Latitude=41.0, Longitude=-3.002)
    events.append(bounce2)

    # Brake below 40
    brake = make_event(base + timedelta(seconds=20), IASKnots=35, Latitude=41.0, Longitude=-3.01)
    events.append(brake)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

    expected_distance = round(haversine(41.0, -3.0, 41.0, -3.01))
    assert result.phase_metrics["LandingVSFpm"] == -300
    assert result.phase_metrics["LandingBounces"] == [-180, -220]
    assert result.phase_metrics["BrakeDistance"] == expected_distance


def test_touchdown_already_below_40_knots(analyzer):
    base = datetime(2025, 7, 6, 14, 0, 0)
    events = []

    touchdown = make_event(base, LandingVSFpm=-150, IASKnots=35, Latitude=42.0, Longitude=-4.0)
    events.append(touchdown)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

    assert result.phase_metrics["LandingVSFpm"] == -150
    assert result.phase_metrics["LandingBounces"] == []
    assert result.phase_metrics["BrakeDistance"] == 0


def test_no_touchdown_raises(analyzer):
    base = datetime(2025, 7, 6, 15, 0, 0)
    events = [make_event(base + timedelta(seconds=i*5), IASKnots=100) for i in range(5)]

    with pytest.raises(RuntimeError, match="Can't find touchdown from landing phase"):
        analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)


def test_no_brake_event_returns_none(analyzer):
    base = datetime(2025, 7, 6, 16, 0, 0)
    events = []

    touchdown = make_event(base, LandingVSFpm=-200, IASKnots=90, Latitude=43.0, Longitude=-5.0)
    events.append(touchdown)

    # Rollout continues but never below 40 knots
    for i in range(5):
        ts = base + timedelta(seconds=(i + 1) * 10)
        events.append(make_event(ts, IASKnots=80 - i*5, Latitude=43.0, Longitude=-5.0 - 0.001*(i+1)))

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)

    assert result.phase_metrics["LandingVSFpm"] == -200
    assert result.phase_metrics["LandingBounces"] == []
    assert result.phase_metrics["BrakeDistance"] == None


@pytest.mark.parametrize("filename, landing_start, landing_end, landing_vs, bounces_str, brake_distance", [
    ("LEPA-LEPP-737.json", "2025-06-14T18:22:03.8839814", "2025-06-14T18:22:43.8757681", "-73", "", "1120"),
    ("LEPP-LEMG-737.json", "2025-06-15T01:08:58.9593068", "2025-06-15T01:09:24.96811", "-329", "", "997"),
    ("LPMA-Circuits-737.json", "2025-06-02T22:13:43.7386248", "2025-06-02T22:14:05.7377146", "-995", "-80", "781"),
    ("UHMA-PAOM-B350.json", "2025-06-16T00:07:26.5753238", "2025-06-16T00:07:44.5761254", "-27", "", "675"),
    ("UHPT-UHMA-B350.json", "2025-06-15T20:01:00.8191063", "2025-06-15T20:03:02.8108667", "-83", "", "766"),
    ("UHPT-UHMA-SF34.json", "2025-06-05T15:05:21.2266523", "2025-06-05T15:07:23.2129155", "-150", "", "1437"),
    ("UHSH-UHMM-B350.json", "2025-05-17T19:41:01.243375", "2025-05-17T19:42:55.2530305", "-121", "", "596"),
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-23T00:15:48.5520445", "2025-06-23T00:16:16.5747404", "-11", "", "1005"),
])
def test_final_landing_analyzer_from_real_files(filename, landing_start, landing_end, landing_vs, bounces_str, brake_distance, analyzer):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = analyzer.analyze(events, parse_timestamp(landing_start), parse_timestamp(landing_end))

    expected_bounces = bounces = [int(x) for x in bounces_str.split("|")] if bounces_str else []    

    assert result.phase_metrics["LandingVSFpm"] == int(landing_vs)
    assert result.phase_metrics["LandingBounces"] == expected_bounces
    assert result.phase_metrics["BrakeDistance"] == int(brake_distance) 
