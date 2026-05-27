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
            "backtrack_4.json",
            "2025-10-09T14:29:24.432449", "2025-10-09T14:30:46.451490",
            "None", "None",
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

    if expected_start != "None" and expected_end != "None":
        assert result is not None, f"Backtrack not detected in {filename}"
        start, end = result
        assert start == parse_timestamp(expected_start), f"Wrong backtrack start in {filename}: got {start}"
        assert end == parse_timestamp(expected_end), f"Wrong backtrack end in {filename}: got {end}"
    else:
        assert result is None, f"Backtrack should not have been detected in {filename}"


# =============================================================================
# detect_from_takeoff — with runway context
#
# When real departure/landing ICAOs are filled in, the detector uses the actual
# runway polygon and expected values may differ from the no-context case.
# =============================================================================

@pytest.mark.parametrize(
    "filename, departure, landing, takeoff_start, takeoff_end, expected_start, expected_end",
    [
        (
            "backtrack_1.json", "EFKS", "EFVA",
            "2025-10-14T17:47:35.335188", "2025-10-14T17:49:29.337924",
            "2025-10-14T17:45:05.338359", "2025-10-14T17:47:35.335187",
        ),
        (
            "backtrack_2.json", "EFKT", "EFKS",
            "2025-10-12T10:54:21.650446", "2025-10-12T10:55:39.648127",
            "2025-10-12T10:53:03.652548", "2025-10-12T10:54:21.650445",
        ),
        (
            "backtrack_3.json", "ENNA", "EFKI",
            "2025-10-10T10:09:23.561285", "2025-10-10T10:11:35.550340",
            "2025-10-10T10:06:47.549293", "2025-10-10T10:09:23.561284",
        ),
        (
            "backtrack_4.json", "ENDU", "ENKR",
            "2025-10-09T14:29:24.432449", "2025-10-09T14:30:46.451490",
            "None", "None",
        ),        
        (
            "backtrack_5.json", "ESNX", "ENRA",
            "2025-10-03T22:44:13.423502", "2025-10-03T22:45:03.426016",
            "2025-10-03T22:42:59.421115", "2025-10-03T22:44:13.423501",
        ),
        (
            "backtrack_6.json", "EFVA", "EETN",
            "2025-10-15T17:17:15.878744", "2025-10-15T17:18:57.884143",
            "2025-10-15 17:13:39.880437", "2025-10-15T17:17:15.878743",
        ),
        (
            "backtrack_7.json", "LEPP", "LEVX",
            "2026-03-19T22:09:36.851354", "2026-03-19T22:11:28.853752",
            "2026-03-19T22:06:28.851052", "2026-03-19T22:09:36.851353",
        ),
        (
            "backtrack_8.json", "CYZF", "CYHY",
            "2026-04-20T22:55:01.058004", "2026-04-20T22:55:41.057312",
            "None", "None",
        ),
        (
            "backtrack_9.json", "HKJK", "FZAA",
            "2026-04-29T17:40:54.011015", "2026-04-29T17:43:20.012574",
            "None", "None",
        ),
        (
            "backtrack_10.json", "CYDL", "PAWG",
            "2026-05-20T00:49:28.220448", "2026-05-20T00:53:10.217650",
            "None", "None",
        ),
        (
            "backtrack_11.json", "LEGE", "LEBB",
            "2026-05-21T23:19:42.714492", "2026-05-21T23:20:32.711203",
            "None", "None",
        ),
        (
            "backtrack_12.json", "CYQH", "CYDL",
            "2026-05-22T12:33:22.011199", "2026-05-22T12:35:36.001005",
            "None", "None",
        ),
        (
            "backtrack_13.json", "CYDL", "PAWG",
            "2026-05-24T22:22:58.743970", "2026-05-24T22:23:44.763895",
            "None", "None",
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

    if expected_start != "None" and expected_end != "None":
        assert result is not None, f"Backtrack not detected in {filename}"
        start, end = result
        assert start == parse_timestamp(expected_start), f"Wrong backtrack start in {filename}: got {start}"
        assert end == parse_timestamp(expected_end), f"Wrong backtrack end in {filename}: got {end}"
    else:
        assert result is None, f"Backtrack should not have been detected in {filename}"


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
            "backtrack_2.json",
            "2025-10-12T11:31:39.505377", "2025-10-12T11:32:47.518130",
            "None", "None",
        ),
        (
            "backtrack_3.json",
            "2025-10-10T10:47:57.550114", "2025-10-10T10:48:45.557813",
            "None", "None",
        ),
        (
            "backtrack_4.json",
            "2025-10-09T15:20:06.432836", "2025-10-09T15:20:46.446648",
            "2025-10-09T15:20:46.446649", "2025-10-09T15:22:14.439817",
        ),        
        (
            "backtrack_5.json",
            "2025-10-03T23:33:49.426287", "2025-10-03T23:33:49.426287",
            "None", "None",
        ),
        (
            "backtrack_6.json",
            "2025-10-15T18:04:41.886649", "2025-10-15T18:05:21.882106",
            "None", "None",
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

    if expected_start != "None" and expected_end != "None":
        assert result is not None, f"Backtrack not detected in {filename}"
        start, end = result
        assert start == parse_timestamp(expected_start), f"Wrong backtrack start in {filename}: got {start}"
        assert end == parse_timestamp(expected_end), f"Wrong backtrack end in {filename}: got {end}"
    else:
        assert result is None, f"Backtrack should not have been detected in {filename}"


# =============================================================================
# detect_from_landing — with runway context
#
# Same note as for takeoff: update expected values when real ICAOs are set.
# =============================================================================

@pytest.mark.parametrize(
    "filename, departure, landing, landing_start, landing_end, expected_start, expected_end",
    [
        (
            "backtrack_1.json", "EFKS", "EFVA",
            "2025-10-14T18:38:47.341642", "2025-10-14T18:39:01.335183",
            "2025-10-14T18:39:01.335184", "2025-10-14T18:42:23.325495",
        ),
        (
            "backtrack_2.json", "EFKT", "EFKS",
            "2025-10-12T11:31:39.505377", "2025-10-12T11:32:47.518130",
            "None", "None",
        ),
        (
            "backtrack_3.json", "ENNA", "EFKI",
            "2025-10-10T10:47:57.550114", "2025-10-10T10:48:45.557813",
            "None", "None",
        ),
        (
            "backtrack_4.json", "ENDU", "ENKR",
            "2025-10-09T15:20:06.432836", "2025-10-09T15:20:46.446648",
            "2025-10-09T15:20:46.446649", "2025-10-09T15:22:14.439817",
        ),        
        (
            "backtrack_5.json", "ESNX", "ENRA",
            "2025-10-03T23:33:49.426287", "2025-10-03T23:33:49.426287",
            "None", "None",
        ),
        (
            "backtrack_6.json", "EFVA", "EETN",
            "2025-10-15T18:04:41.886649", "2025-10-15T18:05:21.882106",
            "None", "None",
        ),
        (
            "backtrack_7.json", "LEPP", "LEVX",
            "2026-03-19T23:15:30.854274", "2026-03-19T23:16:14.850904",
            "2026-03-1923:16:14.850905", "2026-03-19T23:19:34",
        ),
        (
            "backtrack_8.json", "CYZF", "CYHY",
            "2026-04-20T23:56:24.995867", "2026-04-20T23:56:42.983436",
            "2026-04-20T23:56:42.983437", "2026-04-21T00:00:30",
        ),
        (
            "backtrack_9.json", "HKJK", "FZAA",
            "2026-04-29T20:42:12.008134", "2026-04-29T20:44:14.014454",
            "2026-04-29T20:44:14.014455", "2026-04-29T20:47:42",
        ),
        (
            "backtrack_10.json", "CYDL", "PAWG",
            "2026-05-20T01:55:14.205334", "2026-05-20T01:55:38.210097",
            "2026-05-20T01:55:38.210098", "2026-05-20T01:57:08",
        ),
        (
            "backtrack_11.json", "LEGE", "LEBB",
            "2026-05-22T00:31:30.698606", "2026-05-22T00:31:44.710527",
            "None", "None",
        ),
        (
            "backtrack_12.json", "CYQH", "CYDL",
            "2026-05-22T13:15:56.021633", "2026-05-22T13:17:30.007264",
            "None", "None",
        ),
        (
            "backtrack_13.json", "CYDL", "PAWG",
            "2026-05-24T23:38:11.097724", "2026-05-24T23:38:31.097996",
            "2026-05-24T23:38:31.097997", "2026-05-24T23:41:23",
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

    if expected_start != "None" and expected_end != "None":
        assert result is not None, f"Backtrack not detected in {filename}"
        start, end = result
        assert start == parse_timestamp(expected_start), f"Wrong backtrack start in {filename}: got {start}"
        assert end == parse_timestamp(expected_end), f"Wrong backtrack end in {filename}: got {end}"
    else:
        assert result is None, f"Backtrack should not have been detected in {filename}"
