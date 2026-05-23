from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.models.flight_context import AirportContext, FlightContext, Runway, RunwayEnd
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.taxi import (
    TaxiAnalyzer,
    PARAM_TAXI_POSITION,
    TAXI_PRE_TAKEOFF,
    TAXI_POST_LANDING,
)
from mam_analyzer.phases.analyzers.issues import Issues
from mam_analyzer.utils.parsing import parse_timestamp
from tests.runway_data import make_flight_context

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)


# Lat increment of ~50 m and ~30 m (pure latitude movement, lon fixed at -3.0).
# haversine(40.0, -3.0, 40.0 + n*0.00045, -3.0) ≈ n * 50 m
# haversine(40.0, -3.0, 40.0 + n*0.00027, -3.0) ≈ n * 30 m
_LAT_BASE = 40.0
_LON_BASE = -3.0
_STEP_50M = 0.00045   # ≈ 50 m per step
_STEP_30M = 0.00027   # ≈ 30 m per step


def _make_taxi_events(base, n_events, lat_step, speeds):
    """
    Create *n_events* taxi events spaced *lat_step* degrees apart starting at
    (_LAT_BASE, _LON_BASE).  *speeds* is a list/dict of {index: speed_knots};
    indices not listed get a safe speed of 20 knots.
    """
    events = []
    for i in range(n_events):
        ts = base + timedelta(seconds=i * 10)
        speed = speeds.get(i, 20)
        ev = make_event(
            ts,
            onGround=True,
            GSKnots=speed,
            Latitude=_LAT_BASE + i * lat_step,
            Longitude=_LON_BASE,
        )
        events.append(ev)
    return events


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def analyzer():
    return TaxiAnalyzer()


# ---------------------------------------------------------------------------
# Baseline tests (no phase_params – legacy behaviour)
# ---------------------------------------------------------------------------

def test_taxi_without_overspeed(analyzer):
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = []

    for i in range(6):
        ts = base + timedelta(seconds=i * 10)
        ev = make_event(
            ts,
            onGround=True,
            GSKnots=20 + (i % 2),
            Latitude=40.0 + i * 0.0001,
            Longitude=-3.0 + i * 0.0001,
        )
        events.append(ev)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)
    assert len(result.phase_metrics) == 0
    assert len(result.issues) == 0

def test_taxi_with_single_overspeed(analyzer):
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = []

    for i in range(6):
        ts = base + timedelta(seconds=i * 10)
        speed = 24
        if i == 3:
            speed = 31
        ev = make_event(
            ts,
            onGround=True,
            GSKnots=speed,
            Latitude=40.0 + i * 0.0001,
            Longitude=-3.0 + i * 0.0001,
        )
        events.append(ev)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)
    assert len(result.phase_metrics) == 0
    assert len(result.issues) == 1
    assert result.issues[0].code == Issues.ISSUE_TAXI_OVERSPEED
    assert result.issues[0].timestamp == base + timedelta(seconds=30)
    assert result.issues[0].value == 31

def test_taxi_with_multiple_overspeed(analyzer):
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = []

    for i in range(8):
        ts = base + timedelta(seconds=i * 10)
        speed = 24
        if i in (2, 4, 6):
            speed = 30 + i
        ev = make_event(
            ts,
            onGround=True,
            GSKnots=speed,
            Latitude=40.0 + i * 0.0001,
            Longitude=-3.0 + i * 0.0001,
        )
        events.append(ev)

    result = analyzer.analyze(events, events[0].timestamp, events[-1].timestamp)
    assert len(result.phase_metrics) == 0
    assert len(result.issues) == 3
    assert result.issues[0].code == Issues.ISSUE_TAXI_OVERSPEED
    assert result.issues[0].timestamp == base + timedelta(seconds=20)
    assert result.issues[0].value == 32
    assert result.issues[1].code == Issues.ISSUE_TAXI_OVERSPEED
    assert result.issues[1].timestamp == base + timedelta(seconds=40)
    assert result.issues[1].value == 34
    assert result.issues[2].code == Issues.ISSUE_TAXI_OVERSPEED
    assert result.issues[2].timestamp == base + timedelta(seconds=60)
    assert result.issues[2].value == 36


# ---------------------------------------------------------------------------
# Pre-takeoff runway-entry exemption (last ~100 m)
# ---------------------------------------------------------------------------
# Layout: ev0 (start, far from runway) → … → ev6 (end, near runway entry)
# With ~50 m spacing (7 events):
#   exempt_from = ev5.timestamp  (ev5 ≈ 50 m from end, ev6 ≈ 0 m from end)
#
# With ~30 m spacing (8 events):
#   exempt_from = ev4.timestamp  (ev4 ≈ 90 m, ev5 ≈ 60 m, ev6 ≈ 30 m, ev7 ≈ 0 m from end)

def test_pre_takeoff_overspeed_outside_exempt_zone_is_reported(analyzer):
    """Overspeed well before the last 100 m → issue reported."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    # ev3 is at ~150 m from the runway end → outside exempt zone
    # ev5 is at ~50 m from the runway end → inside exempt zone (not reported)
    events = _make_taxi_events(base, 7, _STEP_50M, {3: 35, 5: 40})

    result = analyzer.analyze(
        events,
        events[0].timestamp,
        events[-1].timestamp,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    assert len(result.issues) == 1
    assert result.issues[0].code == Issues.ISSUE_TAXI_OVERSPEED
    assert result.issues[0].timestamp == base + timedelta(seconds=30)
    assert result.issues[0].value == 35


def test_pre_takeoff_overspeed_only_in_exempt_zone_not_reported(analyzer):
    """Overspeed exclusively in the last ~100 m → no issue."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    # Both overspeeds are inside the exempt zone (ev5 ≈ 50 m, ev6 ≈ 0 m from end)
    events = _make_taxi_events(base, 7, _STEP_50M, {5: 35, 6: 40})

    result = analyzer.analyze(
        events,
        events[0].timestamp,
        events[-1].timestamp,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    assert len(result.issues) == 0


def test_pre_takeoff_overspeed_mixed_only_outside_reported(analyzer):
    """Overspeed both inside and outside the last ~100 m: only outside is reported.

    8 events with ~30 m spacing → exempt_from = ev4.timestamp
    (events 4-7 are within ~90 m of the runway entry).
    """
    base = datetime(2025, 7, 6, 12, 0, 0)
    # ev2 at ~150 m from end → reported
    # ev5 at ~60 m from end (exempt) → not reported
    events = _make_taxi_events(base, 8, _STEP_30M, {2: 35, 5: 42})

    result = analyzer.analyze(
        events,
        events[0].timestamp,
        events[-1].timestamp,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    assert len(result.issues) == 1
    assert result.issues[0].code == Issues.ISSUE_TAXI_OVERSPEED
    assert result.issues[0].timestamp == base + timedelta(seconds=20)
    assert result.issues[0].value == 35


def test_pre_takeoff_entire_taxi_under_100m_all_exempt(analyzer):
    """Taxi shorter than 100 m → every event is in the exempt zone."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    # 4 events × ~30 m = ~90 m total; all should be exempt
    events = _make_taxi_events(base, 4, _STEP_30M, {0: 35, 1: 40, 2: 38, 3: 45})

    result = analyzer.analyze(
        events,
        events[0].timestamp,
        events[-1].timestamp,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    assert len(result.issues) == 0


def test_pre_takeoff_no_location_data_overspeed_reported(analyzer):
    """Without lat/lon data the exemption cannot be computed → overspeed is reported."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = []
    for i in range(6):
        ts = base + timedelta(seconds=i * 10)
        speed = 35 if i >= 4 else 20
        # Intentionally omit Latitude/Longitude
        ev = make_event(ts, onGround=True, GSKnots=speed)
        events.append(ev)

    result = analyzer.analyze(
        events,
        events[0].timestamp,
        events[-1].timestamp,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    # 2 overspeed events (i=4 and i=5) should be reported because no location → no exemption
    assert len(result.issues) == 2
    for issue in result.issues:
        assert issue.code == Issues.ISSUE_TAXI_OVERSPEED


# ---------------------------------------------------------------------------
# Post-landing runway-exit exemption (first ~100 m)
# ---------------------------------------------------------------------------
# Layout: ev0 (start, near runway exit) → … → ev6 (end, far from runway)
# With ~50 m spacing (7 events):
#   exempt_until = ev1.timestamp  (ev0 ≈ 0 m, ev1 ≈ 50 m from start)
#
# With ~30 m spacing (8 events):
#   exempt_until = ev3.timestamp  (ev0–ev3 span ~90 m from start)

def test_post_landing_overspeed_outside_exempt_zone_is_reported(analyzer):
    """Overspeed well after the first 100 m → issue reported."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    # ev4 is at ~200 m from start → outside exempt zone
    # ev1 is at ~50 m from start → inside exempt zone (not reported)
    events = _make_taxi_events(base, 7, _STEP_50M, {1: 38, 4: 35})

    result = analyzer.analyze(
        events,
        events[0].timestamp,
        events[-1].timestamp,
        phase_params={PARAM_TAXI_POSITION: TAXI_POST_LANDING},
    )

    assert len(result.issues) == 1
    assert result.issues[0].code == Issues.ISSUE_TAXI_OVERSPEED
    assert result.issues[0].timestamp == base + timedelta(seconds=40)
    assert result.issues[0].value == 35


def test_post_landing_overspeed_only_in_exempt_zone_not_reported(analyzer):
    """Overspeed exclusively in the first ~100 m → no issue."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    # Both overspeeds inside the exempt zone (ev0 ≈ 0 m, ev1 ≈ 50 m from start)
    events = _make_taxi_events(base, 7, _STEP_50M, {0: 35, 1: 40})

    result = analyzer.analyze(
        events,
        events[0].timestamp,
        events[-1].timestamp,
        phase_params={PARAM_TAXI_POSITION: TAXI_POST_LANDING},
    )

    assert len(result.issues) == 0


def test_post_landing_overspeed_mixed_only_outside_reported(analyzer):
    """Overspeed both inside and outside the first ~100 m: only outside is reported.

    8 events with ~30 m spacing → exempt_until = ev3.timestamp
    (events 0-3 are within ~90 m of the runway exit).
    """
    base = datetime(2025, 7, 6, 12, 0, 0)
    # ev2 at ~60 m from start (exempt) → not reported
    # ev5 at ~150 m from start → reported
    events = _make_taxi_events(base, 8, _STEP_30M, {2: 42, 5: 35})

    result = analyzer.analyze(
        events,
        events[0].timestamp,
        events[-1].timestamp,
        phase_params={PARAM_TAXI_POSITION: TAXI_POST_LANDING},
    )

    assert len(result.issues) == 1
    assert result.issues[0].code == Issues.ISSUE_TAXI_OVERSPEED
    assert result.issues[0].timestamp == base + timedelta(seconds=50)
    assert result.issues[0].value == 35


def test_post_landing_entire_taxi_under_100m_all_exempt(analyzer):
    """Taxi shorter than 100 m → every event is in the exempt zone."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    # 4 events × ~30 m = ~90 m total; all should be exempt
    events = _make_taxi_events(base, 4, _STEP_30M, {0: 35, 1: 40, 2: 38, 3: 45})

    result = analyzer.analyze(
        events,
        events[0].timestamp,
        events[-1].timestamp,
        phase_params={PARAM_TAXI_POSITION: TAXI_POST_LANDING},
    )

    assert len(result.issues) == 0


def test_post_landing_no_location_data_overspeed_reported(analyzer):
    """Without lat/lon data the exemption cannot be computed → overspeed is reported."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = []
    for i in range(6):
        ts = base + timedelta(seconds=i * 10)
        speed = 35 if i <= 1 else 20
        # Intentionally omit Latitude/Longitude
        ev = make_event(ts, onGround=True, GSKnots=speed)
        events.append(ev)

    result = analyzer.analyze(
        events,
        events[0].timestamp,
        events[-1].timestamp,
        phase_params={PARAM_TAXI_POSITION: TAXI_POST_LANDING},
    )

    # 2 overspeed events (i=0 and i=1) are reported because no location → no exemption
    assert len(result.issues) == 2
    for issue in result.issues:
        assert issue.code == Issues.ISSUE_TAXI_OVERSPEED


# ---------------------------------------------------------------------------
# Runway-polygon exemption (context-based)
# ---------------------------------------------------------------------------
#
# Test runway: N/S, from (40.0, -3.0) [south end "01"] to (40.01, -3.0) [north
# end "19"], 45 m wide, ~1111 m long.
#
# Positions used:
#   ON_RUNWAY  = (40.005, -3.0)    → centreline midpoint, always inside
#   OFF_RUNWAY = (40.005, -3.005)  → ~400 m from centreline, always outside
#
# A second parallel runway (E/W, "10/28") is placed well away so the two
# footprints never overlap.

_RWY_NS = Runway(
    designators="01/19",
    width_m=45,
    length_m=1111,
    ends=[
        RunwayEnd(designator="01", latitude=40.0,  longitude=-3.0,
                  true_heading_deg=0,   displaced_threshold_m=0, stopway_m=0),
        RunwayEnd(designator="19", latitude=40.01, longitude=-3.0,
                  true_heading_deg=180, displaced_threshold_m=0, stopway_m=0),
    ],
)

_RWY_EW = Runway(
    designators="10/28",
    width_m=45,
    length_m=900,
    ends=[
        RunwayEnd(designator="10", latitude=40.02, longitude=-3.01,
                  true_heading_deg=90,  displaced_threshold_m=0, stopway_m=0),
        RunwayEnd(designator="28", latitude=40.02, longitude=-3.002,
                  true_heading_deg=270, displaced_threshold_m=0, stopway_m=0),
    ],
)

_LAT_ON_RUNWAY  = 40.005   # centreline midpoint of _RWY_NS
_LON_ON_RUNWAY  = -3.0
_LAT_OFF_RUNWAY = 40.005   # same latitude, well off to the side
_LON_OFF_RUNWAY = -3.005


def _make_airport(runways):
    return AirportContext(icao="TEST", runways=runways)


def _make_context(departure_runways=None, landing_runways=None):
    dep = _make_airport(departure_runways or [])
    land = _make_airport(landing_runways or [])
    return FlightContext(departure=dep, destination=land, landing=land)


def test_runway_polygon_pre_takeoff_on_runway_not_reported(analyzer):
    """Overspeed while physically on the departure runway → exempt."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = [
        make_event(base,                       onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
        make_event(base + timedelta(seconds=10), onGround=True, GSKnots=35,
                   Latitude=_LAT_ON_RUNWAY,  Longitude=_LON_ON_RUNWAY),   # on runway, GS > 30
        make_event(base + timedelta(seconds=20), onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
    ]
    ctx = _make_context(departure_runways=[_RWY_NS])

    result = analyzer.analyze(
        events, events[0].timestamp, events[-1].timestamp,
        context=ctx,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    assert len(result.issues) == 0


def test_runway_polygon_pre_takeoff_off_runway_reported(analyzer):
    """Overspeed off any runway at the departure airport → reported."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = [
        make_event(base,                       onGround=True, GSKnots=20,
                   Latitude=_LAT_ON_RUNWAY, Longitude=_LON_ON_RUNWAY),
        make_event(base + timedelta(seconds=10), onGround=True, GSKnots=35,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),  # off runway, GS > 30
        make_event(base + timedelta(seconds=20), onGround=True, GSKnots=20,
                   Latitude=_LAT_ON_RUNWAY, Longitude=_LON_ON_RUNWAY),
    ]
    ctx = _make_context(departure_runways=[_RWY_NS])

    result = analyzer.analyze(
        events, events[0].timestamp, events[-1].timestamp,
        context=ctx,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    assert len(result.issues) == 1
    assert result.issues[0].code == Issues.ISSUE_TAXI_OVERSPEED
    assert result.issues[0].value == 35


def test_runway_polygon_pre_takeoff_no_context_reported(analyzer):
    """Without context there is no runway data → overspeed on the runway position is reported."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = [
        make_event(base,                       onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
        make_event(base + timedelta(seconds=10), onGround=True, GSKnots=35,
                   Latitude=_LAT_ON_RUNWAY,  Longitude=_LON_ON_RUNWAY),
        make_event(base + timedelta(seconds=20), onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
    ]

    result = analyzer.analyze(
        events, events[0].timestamp, events[-1].timestamp,
        context=None,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    assert len(result.issues) == 1
    assert result.issues[0].value == 35


def test_runway_polygon_pre_takeoff_second_runway_exempt(analyzer):
    """Overspeed on a parallel runway (not the active one) → also exempt."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    # Midpoint of _RWY_EW
    lat_rwy2 = (_RWY_EW.ends[0].latitude  + _RWY_EW.ends[1].latitude)  / 2
    lon_rwy2 = (_RWY_EW.ends[0].longitude + _RWY_EW.ends[1].longitude) / 2
    events = [
        make_event(base,                       onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
        make_event(base + timedelta(seconds=10), onGround=True, GSKnots=35,
                   Latitude=lat_rwy2, Longitude=lon_rwy2),  # on second runway
        make_event(base + timedelta(seconds=20), onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
    ]
    ctx = _make_context(departure_runways=[_RWY_NS, _RWY_EW])

    result = analyzer.analyze(
        events, events[0].timestamp, events[-1].timestamp,
        context=ctx,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    assert len(result.issues) == 0


def test_runway_polygon_pre_takeoff_uses_departure_not_landing(analyzer):
    """The pre-takeoff check uses the departure airport runways, not the landing airport."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = [
        make_event(base,                       onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
        make_event(base + timedelta(seconds=10), onGround=True, GSKnots=35,
                   Latitude=_LAT_ON_RUNWAY,  Longitude=_LON_ON_RUNWAY),
        make_event(base + timedelta(seconds=20), onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
    ]
    # _RWY_NS is only at the landing airport, departure has no runways
    ctx = _make_context(departure_runways=[], landing_runways=[_RWY_NS])

    result = analyzer.analyze(
        events, events[0].timestamp, events[-1].timestamp,
        context=ctx,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    assert len(result.issues) == 1


def test_runway_polygon_post_landing_on_runway_not_reported(analyzer):
    """Overspeed while physically on the landing runway → exempt."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = [
        make_event(base,                       onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
        make_event(base + timedelta(seconds=10), onGround=True, GSKnots=35,
                   Latitude=_LAT_ON_RUNWAY,  Longitude=_LON_ON_RUNWAY),
        make_event(base + timedelta(seconds=20), onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
    ]
    ctx = _make_context(landing_runways=[_RWY_NS])

    result = analyzer.analyze(
        events, events[0].timestamp, events[-1].timestamp,
        context=ctx,
        phase_params={PARAM_TAXI_POSITION: TAXI_POST_LANDING},
    )

    assert len(result.issues) == 0


def test_runway_polygon_post_landing_uses_landing_not_departure(analyzer):
    """The post-landing check uses the landing airport runways, not the departure airport."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = [
        make_event(base,                       onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
        make_event(base + timedelta(seconds=10), onGround=True, GSKnots=35,
                   Latitude=_LAT_ON_RUNWAY,  Longitude=_LON_ON_RUNWAY),
        make_event(base + timedelta(seconds=20), onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
    ]
    # _RWY_NS only at departure, landing has no runways
    ctx = _make_context(departure_runways=[_RWY_NS], landing_runways=[])

    result = analyzer.analyze(
        events, events[0].timestamp, events[-1].timestamp,
        context=ctx,
        phase_params={PARAM_TAXI_POSITION: TAXI_POST_LANDING},
    )

    assert len(result.issues) == 1


def test_runway_polygon_post_landing_uses_destination_when_no_landing(analyzer):
    """When context.landing is None, the destination airport is used instead."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    events = [
        make_event(base,                       onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
        make_event(base + timedelta(seconds=10), onGround=True, GSKnots=35,
                   Latitude=_LAT_ON_RUNWAY,  Longitude=_LON_ON_RUNWAY),
        make_event(base + timedelta(seconds=20), onGround=True, GSKnots=20,
                   Latitude=_LAT_OFF_RUNWAY, Longitude=_LON_OFF_RUNWAY),
    ]
    dep = _make_airport([])
    dest = _make_airport([_RWY_NS])
    ctx = FlightContext(departure=dep, destination=dest, landing=None)

    result = analyzer.analyze(
        events, events[0].timestamp, events[-1].timestamp,
        context=ctx,
        phase_params={PARAM_TAXI_POSITION: TAXI_POST_LANDING},
    )

    assert len(result.issues) == 0


def test_runway_polygon_event_without_location_not_exempt(analyzer):
    """An event with GS > 30 but no lat/lon cannot be checked against the runway polygon
    and is only exempt if it falls within the distance-based zone."""
    base = datetime(2025, 7, 6, 12, 0, 0)
    # Single event: overspeed, no position → not in distance-based zone either
    # (distance zone needs at least 2 location events to be computed)
    events = [
        make_event(base,                       onGround=True, GSKnots=35),
        make_event(base + timedelta(seconds=10), onGround=True, GSKnots=35),
    ]
    ctx = _make_context(departure_runways=[_RWY_NS])

    result = analyzer.analyze(
        events, events[0].timestamp, events[-1].timestamp,
        context=ctx,
        phase_params={PARAM_TAXI_POSITION: TAXI_PRE_TAKEOFF},
    )

    assert len(result.issues) == 2


# ---------------------------------------------------------------------------
# Integration-style tests against real flight data files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename, taxi_start, taxi_end, taxi_position", [
    # Pre-takeoff: overspeed near runway entry must be suppressed
    ("entering_runway.json", "2026-03-27T17:02:46.519524", "2026-03-27T17:11:18.519451", TAXI_PRE_TAKEOFF),
    # Post-landing: overspeed near runway exit must be suppressed
    ("leaving_runway.json", "2026-04-08T23:52:58.670121", "2026-04-08T23:55:44.671388", TAXI_POST_LANDING),
])
def test_runway_entry_exit_overspeed_suppressed(filename, taxi_start, taxi_end, taxi_position, analyzer):
    """Overspeed events within ~100 m of runway entry/exit must not be reported."""
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = analyzer.analyze(
        events,
        parse_timestamp(taxi_start),
        parse_timestamp(taxi_end),
        phase_params={PARAM_TAXI_POSITION: taxi_position},
    )

    assert len(result.phase_metrics) == 0
    assert len(result.issues) == 0, (
        f"Expected no overspeed issues for {filename} ({taxi_position}), "
        f"got {len(result.issues)}: {[(i.value, i.timestamp) for i in result.issues]}"
    )


@pytest.mark.parametrize("filename, taxi_start, taxi_end, overspeed_taxi_str", [
    ("LEPA-LEPP-737.json", "2025-06-14T17:10:41.905205", "2025-06-14T17:17:35.879138", ""),
    ("LEPA-LEPP-737.json", "2025-06-14T18:22:43.875769", "2025-06-14T18:26:59.877935", ""),
    ("LEPP-LEMG-737.json", "2025-06-14T23:46:28.960507", "2025-06-14T23:49:32.958062", ""),
    ("LEPP-LEMG-737.json", "2025-06-15T01:09:24.968111", "2025-06-15T01:11:26.954066", ""),
    ("LPMA-Circuits-737.json", "2025-06-02T21:43:03.739527", "2025-06-02T21:47:57.737803", ""),
    ("UHMA-PAOM-B350.json", "2025-06-15T22:16:58.578381", "2025-06-15T22:19:44.582974", ""),
    ("UHMA-PAOM-B350.json", "2025-06-16T00:07:44.576126", "2025-06-16T00:12:10.586580", ""),
    ("UHPT-UHMA-B350.json", "2025-06-15T18:12:32.825495", "2025-06-15T18:17:20.817033", ""),
    ("UHPT-UHMA-B350.json", "2025-06-15T20:03:02.810867", "2025-06-15T20:09:06.816801", ""),
    ("UHPT-UHMA-SF34.json", "2025-06-05T13:03:33.236165", "2025-06-05T13:07:59.224559", ""),
    ("UHPT-UHMA-SF34.json", "2025-06-05T15:07:23.212916", "2025-06-05T15:10:25.234294", ""),
    ("UHSH-UHMM-B350.json", "2025-05-17T17:52:11.248830", "2025-05-17T17:55:53.265563", ""),
    ("UHSH-UHMM-B350.json", "2025-05-17T19:42:55.253031", "2025-05-17T19:44:49.246589", ""),
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-22T22:22:52.551736", "2025-06-22T22:24:54.563528", ""),
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-23T00:16:16.574741", "2025-06-23T00:24:58.562115", ""),
    ("LEVD-fast-crash.json", "2025-09-16T17:20:06.84688", "2025-09-16T17:20:42.855282", "36|50"),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T22:42:53.319156", "2025-07-04T22:47:29.326812", ""),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:44:13.316487", "2025-07-04T23:44:15.327441", ""),
])
def test_final_landing_analyzer_from_real_files(filename, taxi_start, taxi_end, overspeed_taxi_str, analyzer):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = analyzer.analyze(events, parse_timestamp(taxi_start), parse_timestamp(taxi_end))

    expected_overspeed_taxi = [int(x) for x in overspeed_taxi_str.split("|")] if overspeed_taxi_str else []

    assert len(result.phase_metrics) == 0
    assert len(result.issues) == len(expected_overspeed_taxi)

    for i in range(len(expected_overspeed_taxi)):
        assert result.issues[i].code == Issues.ISSUE_TAXI_OVERSPEED
        assert result.issues[i].value == expected_overspeed_taxi[i]


# ---------------------------------------------------------------------------
# Integration tests: runway-polygon exemption against real flight data files
# These cases require airport runway context to suppress the false positive.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename, taxi_start, taxi_end, taxi_position, departure_icao, landing_icao", [
    # Bad-backtrack on the same runway: aircraft taxied on the runway after landing
    # at FZAA; without runway-polygon exemption a spurious TAXI_OVERSPEED would fire.
    (
        "bad_backtrack_same_runway.json",
        "2026-04-29T20:44:46.015966", "2026-04-29T20:48:30.018146",
        TAXI_POST_LANDING, "HKJK", "FZAA",
    ),
    (
        "taxi_other_runway.json",
        "2026-05-03T14:32:47.252341", "2026-05-03T14:39:17.261637",
        TAXI_POST_LANDING, "HUEN", "HAAB",
    ),
])
def test_runway_polygon_suppresses_overspeed_real_files(
    filename, taxi_start, taxi_end, taxi_position, departure_icao, landing_icao, analyzer
):
    """Overspeed while taxiing on a runway must not be reported when runway context is available."""
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    ctx = make_flight_context(departure_icao, landing_icao)

    result = analyzer.analyze(
        events,
        parse_timestamp(taxi_start),
        parse_timestamp(taxi_end),
        context=ctx,
        phase_params={PARAM_TAXI_POSITION: taxi_position},
    )

    assert len(result.issues) == 0, (
        f"Expected no overspeed issues for {filename} ({taxi_position}), "
        f"got {len(result.issues)}: {[(i.value, i.timestamp) for i in result.issues]}"
    )
