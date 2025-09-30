from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.taxi import TaxiAnalyzer
from mam_analyzer.phases.analyzers.issues import Issues
from mam_analyzer.utils.parsing import parse_timestamp


def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)


@pytest.fixture
def analyzer():
    return TaxiAnalyzer()

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
            speed = 30
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
    assert result.issues[0].value == 30

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



@pytest.mark.parametrize("filename, taxi_start, taxi_end, overspeed_taxi_str", [
    ("LEPA-LEPP-737.json", "2025-06-14T17:10:41.905205", "2025-06-14T17:17:35.879138", ""),
    ("LEPA-LEPP-737.json", "2025-06-14T18:22:43.875769", "2025-06-14T18:26:59.877935", "27"),
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