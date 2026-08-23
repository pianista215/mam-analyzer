from datetime import datetime, timedelta

import pytest

from mam_analyzer.evaluator import FlightEvaluator
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.issues import Issues
from mam_analyzer.phases.analyzers.result import AnalysisResult
from mam_analyzer.phases.flight_phase import FlightPhase


def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)


def make_phase(name, events):
    return FlightPhase(name, events[0].timestamp, events[-1].timestamp, AnalysisResult(), events)


@pytest.fixture
def evaluator():
    return FlightEvaluator()


def test_calculate_zfw_stable_value(evaluator):
    base = datetime(2026, 1, 1, 10, 0, 0)
    startup = make_phase("startup", [
        make_event(base, ZFW=1000),
        make_event(base + timedelta(seconds=30)),
    ])
    taxi = make_phase("taxi", [
        make_event(base + timedelta(minutes=1)),
        make_event(base + timedelta(minutes=2)),
    ])
    takeoff = make_phase("takeoff", [
        make_event(base + timedelta(minutes=3)),
    ])

    zfw = evaluator.calculate_zfw([startup, taxi, takeoff])

    assert zfw == 1000


def test_calculate_zfw_boarding_during_taxi(evaluator):
    """Some aircraft "board" passengers already rolling in taxi: the ZFW change
    happens after engine start, so the last value before takeoff must win."""
    base = datetime(2026, 1, 1, 10, 0, 0)
    startup = make_phase("startup", [
        make_event(base, ZFW=1000),
        make_event(base + timedelta(seconds=30)),
    ])
    taxi = make_phase("taxi", [
        make_event(base + timedelta(minutes=1)),
        make_event(base + timedelta(minutes=2), ZFW=1200),
        make_event(base + timedelta(minutes=3)),
    ])
    takeoff = make_phase("takeoff", [
        make_event(base + timedelta(minutes=4)),
    ])

    zfw = evaluator.calculate_zfw([startup, taxi, takeoff])

    assert zfw == 1200


def test_calculate_zfw_looks_back_through_multiple_pretakeoff_phases(evaluator):
    base = datetime(2026, 1, 1, 10, 0, 0)
    startup = make_phase("startup", [make_event(base, ZFW=1000)])
    taxi1 = make_phase("taxi", [make_event(base + timedelta(minutes=1))])
    backtrack = make_phase("backtrack", [make_event(base + timedelta(minutes=2), ZFW=1300)])
    taxi2 = make_phase("taxi", [make_event(base + timedelta(minutes=3))])
    takeoff = make_phase("takeoff", [make_event(base + timedelta(minutes=4))])

    zfw = evaluator.calculate_zfw([startup, taxi1, backtrack, taxi2, takeoff])

    assert zfw == 1300


def test_calculate_zfw_returns_none_without_zfw_data(evaluator):
    base = datetime(2026, 1, 1, 10, 0, 0)
    startup = make_phase("startup", [make_event(base)])
    taxi = make_phase("taxi", [make_event(base + timedelta(minutes=1))])
    takeoff = make_phase("takeoff", [make_event(base + timedelta(minutes=2))])

    zfw = evaluator.calculate_zfw([startup, taxi, takeoff])

    assert zfw is None


def test_calculate_zfw_returns_none_without_takeoff_phase(evaluator):
    base = datetime(2026, 1, 1, 10, 0, 0)
    startup = make_phase("startup", [make_event(base, ZFW=1000)])

    zfw = evaluator.calculate_zfw([startup])

    assert zfw is None


def test_check_zfw_changed_ignores_change_in_pretakeoff_taxi(evaluator):
    base = datetime(2026, 1, 1, 10, 0, 0)
    startup = make_phase("startup", [make_event(base, ZFW=1000)])
    taxi = make_phase("taxi", [make_event(base + timedelta(minutes=1), ZFW=1200)])
    takeoff = make_phase("takeoff", [make_event(base + timedelta(minutes=2))])
    cruise = make_phase("cruise", [make_event(base + timedelta(minutes=10))])
    landing = make_phase("final_landing", [make_event(base + timedelta(minutes=20))])

    evaluator.check_zfw_changed([startup, taxi, takeoff, cruise, landing], initial_zfw=1200)

    assert taxi.analysis.issues == []
    assert startup.analysis.issues == []


def test_check_zfw_changed_ignores_change_in_postlanding_taxi_and_shutdown(evaluator):
    base = datetime(2026, 1, 1, 10, 0, 0)
    takeoff = make_phase("takeoff", [make_event(base)])
    cruise = make_phase("cruise", [make_event(base + timedelta(minutes=10))])
    landing = make_phase("final_landing", [make_event(base + timedelta(minutes=20))])
    taxi = make_phase("taxi", [make_event(base + timedelta(minutes=21), ZFW=900)])
    shutdown = make_phase("shutdown", [make_event(base + timedelta(minutes=22), ZFW=850)])

    evaluator.check_zfw_changed([takeoff, cruise, landing, taxi, shutdown], initial_zfw=1200)

    assert taxi.analysis.issues == []
    assert shutdown.analysis.issues == []


def test_check_zfw_changed_flags_inflight_change(evaluator):
    base = datetime(2026, 1, 1, 10, 0, 0)
    takeoff = make_phase("takeoff", [make_event(base)])
    cruise = make_phase("cruise", [make_event(base + timedelta(minutes=10), ZFW=5000)])
    landing = make_phase("final_landing", [make_event(base + timedelta(minutes=20))])

    evaluator.check_zfw_changed([takeoff, cruise, landing], initial_zfw=1200)

    assert len(cruise.analysis.issues) == 1
    assert cruise.analysis.issues[0].code == Issues.ISSUE_ZFW_MODIFIED
    assert cruise.analysis.issues[0].value == 5000
