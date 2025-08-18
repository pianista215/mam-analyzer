from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.approach import ApproachAnalyzer
from mam_analyzer.utils.parsing import parse_timestamp


def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)

@pytest.fixture
def analyzer():
    return ApproachAnalyzer()

def test_analyze_basic_case(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=5)

    events = [
        make_event(start_time + timedelta(seconds=0), VSFpm=-500),
        make_event(start_time + timedelta(seconds=30), VSFpm=-700),
        make_event(start_time + timedelta(seconds=60), VSFpm=-600),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    expected = [
        ("MinVSFpm", -700),
        ("MaxVSFpm", -500),
        ("AvgVSFpm", -600),
    ]
    assert result == expected


def test_analyze_only_one_event(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=0), VSFpm=-800),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    expected = [
        ("MinVSFpm", -800),
        ("MaxVSFpm", -800),
        ("AvgVSFpm", -800),
    ]
    assert result == expected


def test_analyze_ignores_events_outside_range(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=2)

    events = [
        make_event(start_time - timedelta(seconds=10), VSFpm=-400),
        make_event(start_time + timedelta(seconds=30), VSFpm=-500),
        make_event(end_time + timedelta(seconds=10), VSFpm=-600),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    expected = [
        ("MinVSFpm", -500),
        ("MaxVSFpm", -500),
        ("AvgVSFpm", -500),
    ]
    assert result == expected


def test_analyze_raises_if_no_vertical_speed(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    # No event with VS
    events = [
        make_event(start_time + timedelta(seconds=10)),
        make_event(start_time + timedelta(seconds=20)),
    ]

    with pytest.raises(RuntimeError, match="Can't retrieve vertical speed"):
        analyzer.analyze(events, start_time, end_time)

@pytest.mark.parametrize("filename, app_start, app_end, min_vs, max_vs, avg_vs", [
    ("LEPA-LEPP-737.json", "2025-06-14T18:19:03.883981", "2025-06-14T18:22:03.883981", "-1903", "322", "-789"),
    ("LEPP-LEMG-737.json", "2025-06-15T01:05:58.959306", "2025-06-15T01:08:58.959306", "-1045", "-219", "-791"),
    ("UHMA-PAOM-B350.json", "2025-06-16T00:04:26.575323", "2025-06-16T00:07:26.575323", "-994", "-44", "-605"),
    ("UHPT-UHMA-B350.json", "2025-06-15T19:58:00.819106", "2025-06-15T20:01:00.819106", "-775", "-279", "-594"),
    ("UHPT-UHMA-SF34.json", "2025-06-05T15:02:21.226652", "2025-06-05T15:05:21.226652", "-1355", "-109", "-670"),
    ("UHSH-UHMM-B350.json", "2025-05-17T19:38:01.243375", "2025-05-17T19:41:01.24337", "-911", "-15", "-640"),
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-23T00:12:48.552044", "2025-06-23T00:15:48.552044", "-708", "59", "-479"),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:04:23.315419", "2025-07-04T23:07:23.315419", "-1904", "795", "-402"),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:44:13.316486", "-6534", "2898", "-208")
])
def test_cruise_analyzer_from_real_files(filename, app_start, app_end, min_vs, max_vs, avg_vs, analyzer):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = analyzer.analyze(events, parse_timestamp(app_start), parse_timestamp(app_end))

    assert result[0] == ('MinVSFpm', int(min_vs))
    assert result[1] == ('MaxVSFpm', int(max_vs))
    assert result[2] == ('AvgVSFpm', int(avg_vs))        
