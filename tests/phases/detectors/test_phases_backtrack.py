import json
import os
from datetime import timedelta
import pytest

from mam_analyzer.phases.detectors.backtrack import BacktrackDetector
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.phases.analyzers.result import AnalysisResult
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.utils.parsing import parse_timestamp
from runway_data import make_flight_context


# === Helpers ===

def _load_events(filename):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [FlightEvent.from_json(e) for e in data["Events"]]


def _make_phase(name, start, end, events):
    filtered = [e for e in events if start <= e.timestamp <= end]
    return FlightPhase(name, start, end, AnalysisResult(), filtered)


def _build_pretakeoff_taxi(events, takeoff_start):
    """Taxi = everything before the takeoff."""
    taxi_start = events[0].timestamp
    taxi_end = takeoff_start - timedelta(microseconds=1)
    return _make_phase("taxi", taxi_start, taxi_end, events)


def _build_postlanding_taxi(events, landing_end):
    """Taxi = everything after the landing."""
    taxi_start = landing_end + timedelta(microseconds=1)
    taxi_end = events[-1].timestamp
    return _make_phase("taxi", taxi_start, taxi_end, events)


@pytest.fixture
def detector():
    return BacktrackDetector()


# =============================================================================
# detect_from_takeoff — without context
#
# expected_start: moment the aircraft enters the runway to backtrack
# expected_end: equals takeoff_start - 1µs (taxi.end)
# =============================================================================

@pytest.mark.parametrize(
    "filename, takeoff_start, takeoff_end, expected_start, expected_end",
    [
        (
            "backtrack_1.json",
            "2025-10-14T17:47:35.335188", "2025-10-14T17:49:29.337924",
            "2025-10-14T17:45:05.338359", "2025-10-14T17:47:35.335187",
        ),
        (
            "backtrack_2.json",
            "2025-10-12T10:54:21.650446", "2025-10-12T10:55:39.648127",
            "2025-10-12T10:53:03.652548", "2025-10-12T10:54:21.650445",
        ),
        (
            "backtrack_3.json",
            "2025-10-10T10:09:23.561285", "2025-10-10T10:11:35.550340",
            "2025-10-10T10:06:47.549293", "2025-10-10T10:09:23.561284",
        ),
        (
            "backtrack_5.json",
            "2025-10-03T22:44:13.423502", "2025-10-03T22:45:03.426016",
            "2025-10-03T22:42:59.421115", "2025-10-03T22:44:13.423501",
        ),
        (
            "backtrack_6.json",
            "2025-10-15T17:17:15.878744", "2025-10-15T17:18:57.884143",
            "2025-10-15T17:13:41.883792", "2025-10-15T17:17:15.878743",
        ),
    ],
)
def test_backtrack_from_takeoff_without_context(
    filename, takeoff_start, takeoff_end, expected_start, expected_end, detector,
):
    events = _load_events(filename)
    takeoff_start_dt = parse_timestamp(takeoff_start)
    taxi = _build_pretakeoff_taxi(events, takeoff_start_dt)
    takeoff = _make_phase("takeoff", takeoff_start_dt, parse_timestamp(takeoff_end), events)

    result = detector.detect_from_takeoff(taxi, takeoff, context=None)

    assert result is not None, f"Backtrack not detected in {filename}"
    start, end = result
    assert start == parse_timestamp(expected_start), f"Wrong backtrack start in {filename}: got {start}"
    assert end == parse_timestamp(expected_end), f"Wrong backtrack end in {filename}: got {end}"


# =============================================================================
# detect_from_takeoff — with runway context
#
# When real departure/landing ICAOs are filled in, the detector uses the actual
# runway polygon and expected values may differ from the no-context case.
# For now, departure/landing are "XXXX" (no runway data); update expected values
# when real ICAOs are set.
# =============================================================================

@pytest.mark.parametrize(
    "filename, departure, landing, takeoff_start, takeoff_end, expected_start, expected_end",
    [
        (
            "backtrack_1.json", "XXXX", "XXXX",
            "2025-10-14T17:47:35.335188", "2025-10-14T17:49:29.337924",
            "2025-10-14T17:45:05.338359", "2025-10-14T17:47:35.335187",
        ),
        (
            "backtrack_2.json", "XXXX", "XXXX",
            "2025-10-12T10:54:21.650446", "2025-10-12T10:55:39.648127",
            "2025-10-12T10:53:03.652548", "2025-10-12T10:54:21.650445",
        ),
        (
            "backtrack_3.json", "XXXX", "XXXX",
            "2025-10-10T10:09:23.561285", "2025-10-10T10:11:35.550340",
            "2025-10-10T10:06:47.549293", "2025-10-10T10:09:23.561284",
        ),
        (
            "backtrack_5.json", "XXXX", "XXXX",
            "2025-10-03T22:44:13.423502", "2025-10-03T22:45:03.426016",
            "2025-10-03T22:42:59.421115", "2025-10-03T22:44:13.423501",
        ),
        (
            "backtrack_6.json", "XXXX", "XXXX",
            "2025-10-15T17:17:15.878744", "2025-10-15T17:18:57.884143",
            "2025-10-15T17:13:41.883792", "2025-10-15T17:17:15.878743",
        ),
        (
            "backtrack_7.json", "LEPP", "LEVX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_8.json", "CYZF", "CYHY",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_9.json", "HKJK", "FZAA",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_10.json", "CYDL", "PAWG",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_11.json", "LEGE", "LEBB",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_12.json", "CYQH", "CYDL",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_13.json", "CYDL", "PAWG",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
    ],
)
def test_backtrack_from_takeoff_with_runways(
    filename, departure, landing, takeoff_start, takeoff_end,
    expected_start, expected_end, detector,
):
    events = _load_events(filename)
    takeoff_start_dt = parse_timestamp(takeoff_start)
    taxi = _build_pretakeoff_taxi(events, takeoff_start_dt)
    takeoff = _make_phase("takeoff", takeoff_start_dt, parse_timestamp(takeoff_end), events)
    ctx = make_flight_context(departure, landing, with_runways=True)

    result = detector.detect_from_takeoff(taxi, takeoff, ctx)

    assert result is not None, f"Backtrack not detected in {filename}"
    start, end = result
    assert start == parse_timestamp(expected_start), f"Wrong backtrack start in {filename}: got {start}"
    assert end == parse_timestamp(expected_end), f"Wrong backtrack end in {filename}: got {end}"


# =============================================================================
# detect_from_landing — without context
#
# expected_start: equals landing_end + 1µs (taxi.start)
# expected_end: moment the aircraft exits the runway after backtracking
# =============================================================================

@pytest.mark.parametrize(
    "filename, landing_start, landing_end, expected_start, expected_end",
    [
        (
            "backtrack_1.json",
            "2025-10-14T18:38:47.341642", "2025-10-14T18:39:01.335183",
            "2025-10-14T18:39:01.335184", "2025-10-14T18:42:23.325495",
        ),
        (
            "backtrack_4.json",
            "2025-10-09T15:20:06.432836", "2025-10-09T15:20:46.446648",
            "2025-10-09T15:20:46.446649", "2025-10-09T15:22:14.439817",
        ),
    ],
)
def test_backtrack_from_landing_without_context(
    filename, landing_start, landing_end, expected_start, expected_end, detector,
):
    events = _load_events(filename)
    landing_end_dt = parse_timestamp(landing_end)
    taxi = _build_postlanding_taxi(events, landing_end_dt)
    landing = _make_phase("final_landing", parse_timestamp(landing_start), landing_end_dt, events)

    result = detector.detect_from_landing(taxi, landing, context=None)

    assert result is not None, f"Backtrack not detected in {filename}"
    start, end = result
    assert start == parse_timestamp(expected_start), f"Wrong backtrack start in {filename}: got {start}"
    assert end == parse_timestamp(expected_end), f"Wrong backtrack end in {filename}: got {end}"


# =============================================================================
# detect_from_landing — with runway context
#
# Same note as for takeoff: update expected values when real ICAOs are set.
# =============================================================================

@pytest.mark.parametrize(
    "filename, departure, landing, landing_start, landing_end, expected_start, expected_end",
    [
        (
            "backtrack_1.json", "XXXX", "XXXX",
            "2025-10-14T18:38:47.341642", "2025-10-14T18:39:01.335183",
            "2025-10-14T18:39:01.335184", "2025-10-14T18:42:23.325495",
        ),
        (
            "backtrack_4.json", "XXXX", "XXXX",
            "2025-10-09T15:20:06.432836", "2025-10-09T15:20:46.446648",
            "2025-10-09T15:20:46.446649", "2025-10-09T15:22:14.439817",
        ),
        (
            "backtrack_7.json", "LEPP", "LEVX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_8.json", "CYZF", "CYHY",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_9.json", "HKJK", "FZAA",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_10.json", "CYDL", "PAWG",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_11.json", "LEGE", "LEBB",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_12.json", "CYQH", "CYDL",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
        (
            "backtrack_13.json", "CYDL", "PAWG",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
            "XXXXXXXXXXX", "XXXXXXXXXXX",
        ),
    ],
)
def test_backtrack_from_landing_with_runways(
    filename, departure, landing, landing_start, landing_end,
    expected_start, expected_end, detector,
):
    events = _load_events(filename)
    landing_end_dt = parse_timestamp(landing_end)
    taxi = _build_postlanding_taxi(events, landing_end_dt)
    landing_phase = _make_phase("final_landing", parse_timestamp(landing_start), landing_end_dt, events)
    ctx = make_flight_context(departure, landing, with_runways=True)

    result = detector.detect_from_landing(taxi, landing_phase, ctx)

    assert result is not None, f"Backtrack not detected in {filename}"
    start, end = result
    assert start == parse_timestamp(expected_start), f"Wrong backtrack start in {filename}: got {start}"
    assert end == parse_timestamp(expected_end), f"Wrong backtrack end in {filename}: got {end}"
