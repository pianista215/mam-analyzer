from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.models.flight_context import AirportContext, FlightContext, Runway, RunwayEnd
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.takeoff import TakeoffAnalyzer
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
    assert result.phase_metrics["TakeoffBounces"] == []
    assert result.phase_metrics["TakeoffGroundDistance"] == expected_distance
    assert result.phase_metrics["TakeoffSpeed"] == 135


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
    assert result.phase_metrics["TakeoffBounces"] == [-120, -180]
    assert result.phase_metrics["TakeoffGroundDistance"] == expected_distance
    assert result.phase_metrics["TakeoffSpeed"] == 150


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
    assert result.phase_metrics["TakeoffBounces"] == []
    assert result.phase_metrics["TakeoffGroundDistance"] == expected_distance
    assert result.phase_metrics["TakeoffSpeed"] == 140


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
    assert result.phase_metrics["TakeoffBounces"] == []
    assert result.phase_metrics["TakeoffGroundDistance"] == expected_distance
    assert result.phase_metrics["TakeoffSpeed"] == 145


@pytest.mark.parametrize("filename, takeoff_start, takeoff_end, bounces_str, takeoff_distance, takeoff_speed", [
    ("LEPA-LEPP-737.json", "2025-06-14T17:17:35.879139", "2025-06-14T17:19:23.8899645", "", "1798", "159"),
    ("LEPP-LEMG-737.json", "2025-06-14T23:49:32.9580634", "2025-06-14T23:51:02.9812455", "", "1368", "154"),
    ("LPMA-Circuits-737.json", "2025-06-02T21:47:57.7378043", "2025-06-02T21:49:51.7385484", "", "1225", "141"),
    ("UHMA-PAOM-B350.json", "2025-06-15T22:19:44.5829755", "2025-06-15T22:20:50.5779508", "", "723", "109"),
    ("UHPT-UHMA-B350.json", "2025-06-15T18:17:20.8170341", "2025-06-15T18:18:16.828107", "", "1366", "101"),
    ("UHPT-UHMA-SF34.json", "2025-06-05T13:07:59.2245609", "2025-06-05T13:09:09.2296981", "", "1111", "125"),
    ("UHSH-UHMM-B350.json", "2025-05-17T17:55:53.265564", "2025-05-17T17:57:09.2445871", "", "1041", "108"),
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-22T22:24:54.5635293", "2025-06-22T22:26:42.5590209", "", "577", "94"),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T22:47:29.3268135", "2025-07-04T22:48:17.3083458", "", "557", "98"),
])
def test_final_landing_analyzer_from_real_files(filename, takeoff_start, takeoff_end, bounces_str, takeoff_distance, takeoff_speed, analyzer):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = analyzer.analyze(events, parse_timestamp(takeoff_start), parse_timestamp(takeoff_end))

    expected_bounces = [int(x) for x in bounces_str.split("|")] if bounces_str else []    

    assert result.phase_metrics["TakeoffBounces"] == expected_bounces
    assert result.phase_metrics["TakeoffGroundDistance"] == int(takeoff_distance)
    assert result.phase_metrics["TakeoffSpeed"] == int(takeoff_speed)


# === Takeoff runway identification tests ===

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


def _make_departure_context(runway):
    return FlightContext(
        departure=AirportContext(icao="TEST", runways=[runway]),
        destination=AirportContext(icao="DEST"),
    )


def test_takeoff_runway_identified_with_context(analyzer):
    base = datetime(2025, 7, 7, 9, 0, 0)

    # Runway heading 90/270, aircraft takes off heading ~90
    rwy = _make_runway(
        lat1=40.0, lon1=-3.010, heading1=90,
        lat2=40.0, lon2=-2.980, heading2=270,
        designator1="09", designator2="27",
        width_m=45, length_m=2600,
    )
    ctx = _make_departure_context(rwy)

    events = [
        make_event(base, Latitude=40.0, Longitude=-3.008, onGround=True, IASKnots=10, Heading=90),
        make_event(base + timedelta(seconds=5), Latitude=40.0, Longitude=-3.005, onGround=True, IASKnots=80, Heading=90),
        make_event(base + timedelta(seconds=10), Latitude=40.0, Longitude=-2.995, onGround=False, IASKnots=135, Heading=90),
    ]

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp, context=ctx)

    assert result.phase_metrics[TakeoffAnalyzer.METRIC_TAKEOFF_RUNWAY] == "09"
    assert TakeoffAnalyzer.METRIC_TAKEOFF_RUNWAY_REMAINING_PCT in result.phase_metrics
    remaining_pct = result.phase_metrics[TakeoffAnalyzer.METRIC_TAKEOFF_RUNWAY_REMAINING_PCT]
    assert 0 <= remaining_pct <= 100


def test_takeoff_runway_not_set_without_context(analyzer):
    base = datetime(2025, 7, 7, 9, 0, 0)
    events = [
        make_event(base, Latitude=40.0, Longitude=-3.0, onGround=True, IASKnots=10, Heading=90),
        make_event(base + timedelta(seconds=10), Latitude=40.0, Longitude=-3.005, onGround=False, IASKnots=135, Heading=90),
    ]

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp, context=None)

    assert TakeoffAnalyzer.METRIC_TAKEOFF_RUNWAY not in result.phase_metrics
    assert TakeoffAnalyzer.METRIC_TAKEOFF_RUNWAY_REMAINING_PCT not in result.phase_metrics


def test_takeoff_runway_not_set_when_no_match(analyzer):
    base = datetime(2025, 7, 7, 9, 0, 0)

    # Runway heading 180/360 but takeoff heading is 90
    rwy = _make_runway(
        lat1=40.0, lon1=-3.0, heading1=180,
        lat2=39.97, lon2=-3.0, heading2=360,
        designator1="18", designator2="36",
    )
    ctx = _make_departure_context(rwy)

    events = [
        make_event(base, Latitude=40.0, Longitude=-3.0, onGround=True, IASKnots=10, Heading=90),
        make_event(base + timedelta(seconds=10), Latitude=40.0, Longitude=-3.005, onGround=False, IASKnots=135, Heading=90),
    ]

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp, context=ctx)

    assert TakeoffAnalyzer.METRIC_TAKEOFF_RUNWAY not in result.phase_metrics
