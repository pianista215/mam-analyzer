from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.approach import ApproachAnalyzer
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
    return ApproachAnalyzer()

def test_analyze_basic_case(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=5)

    events = [
        make_event(start_time + timedelta(seconds=0), VSFpm=-500),
        make_event(start_time + timedelta(seconds=30), VSFpm=-700),
        make_event(start_time + timedelta(seconds=60), VSFpm=-600),
        make_event(end_time - timedelta(seconds=50), VSFpm=-400),
        make_event(end_time - timedelta(seconds=10), VSFpm=-300),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    expected = {
        "MinVSFpm": -700,
        "MaxVSFpm": -300,
        "AvgVSFpm": -500,
        "LastMinuteMinVSFpm": -400,
        "LastMinuteMaxVSFpm": -300,
        "LastMinuteAvgVSFpm": -350,
    }
    assert result.phase_metrics == expected
    assert len(result.issues) == 0


def test_analyze_only_one_event(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=0), VSFpm=-800),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    expected = {
        "MinVSFpm": -800,
        "MaxVSFpm": -800,
        "AvgVSFpm": -800,
        "LastMinuteMinVSFpm": -800,
        "LastMinuteMaxVSFpm": -800,
        "LastMinuteAvgVSFpm": -800,
    }
    assert result.phase_metrics == expected
    assert len(result.issues) == 0


def test_analyze_ignores_events_outside_range(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=2)

    events = [
        make_event(start_time - timedelta(seconds=10), VSFpm=-400),   # out
        make_event(start_time + timedelta(seconds=30), VSFpm=-500),   # in
        make_event(end_time - timedelta(seconds=30), VSFpm=-600),     # in and last minute
        make_event(end_time + timedelta(seconds=10), VSFpm=-700),     # out
    ]

    result = analyzer.analyze(events, start_time, end_time)

    expected = {
        "MinVSFpm": -600,
        "MaxVSFpm": -500,
        "AvgVSFpm": -550,
        "LastMinuteMinVSFpm": -600,
        "LastMinuteMaxVSFpm": -600,
        "LastMinuteAvgVSFpm": -600,
    }
    assert result.phase_metrics == expected
    assert len(result.issues) == 0


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
        
def test_analyze_raises_if_no_vertical_speed_last_minute(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=2)

    # One event, out of the last minute
    events = [
        make_event(start_time + timedelta(seconds=30), VSFpm=-500),
    ]

    with pytest.raises(RuntimeError, match="Can't retrieve vertical speed from approach phase last minute"):
        analyzer.analyze(events, start_time, end_time)

def test_issue_low_vs_below_1000agl(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1200, AGLAltitude=900),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-1200|900"


def test_issue_low_vs_below_2000agl(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=20), VSFpm=-2500, AGLAltitude=1500),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL)
    assert issue.value == "-2500|1500"        


@pytest.mark.parametrize("filename, app_start, app_end, min_vs, max_vs, avg_vs, last_min_min_vs, last_min_max_vs, last_min_avg_vs, one_thousand_issue, two_thousand_issue", [
    ("LEPA-LEPP-737.json", "2025-06-14T18:19:03.883981", "2025-06-14T18:22:03.883981", "-1903", "322", "-789", "-906", "-121", "-610", "-1903|999|-1121|702|-1335|660", ""),
    ("LEPP-LEMG-737.json", "2025-06-15T01:05:58.959306", "2025-06-15T01:08:58.959306", "-1045", "-219", "-791", "-976", "-219", "-626", "", ""),
    ("UHMA-PAOM-B350.json", "2025-06-16T00:04:26.575323", "2025-06-16T00:07:26.575323", "-994", "-44", "-605", "-994", "-44", "-539", "", ""),
    ("UHPT-UHMA-B350.json", "2025-06-15T19:58:00.819106", "2025-06-15T20:01:00.819106", "-775", "-279", "-594", "-775", "-279", "-616", "", ""),
    ("UHPT-UHMA-SF34.json", "2025-06-05T15:02:21.226652", "2025-06-05T15:05:21.226652", "-1355", "-109", "-670", "-1355", "-109", "-720", "-1081|592|-1228|536|-1355|454|-1091|315", ""),
    ("UHSH-UHMM-B350.json", "2025-05-17T19:38:01.243375", "2025-05-17T19:41:01.24337", "-911", "-15", "-640", "-911", "-15", "-611", "", ""),
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-23T00:12:48.552044", "2025-06-23T00:15:48.552044", "-708", "59", "-479", "-658", "59", "-394", "", ""),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:04:23.315419", "2025-07-04T23:07:23.315419", "-1904", "795", "-402", "-899", "-256", "-537", "-1532|788|-1904|724|-1032|690", ""),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:44:13.316486", "-6534", "2898", "-208", "-1531", "-442", "-965", "-6534|744|-4571|519|-2355|794|-1750|918|-1650|832|-1116|775|-1165|719|-1144|602|-1545|430|-1600|380|-1008|730|-1077|646|-1531|497|-1497|451|-1073|236", "-4140|1136|-2205|1253")
])
def test_approach_analyzer_from_real_files(filename, app_start, app_end, min_vs, max_vs, avg_vs, last_min_min_vs, last_min_max_vs, last_min_avg_vs, one_thousand_issue, two_thousand_issue, analyzer):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = analyzer.analyze(events, parse_timestamp(app_start), parse_timestamp(app_end))

    assert result.phase_metrics['MinVSFpm'] == int(min_vs)
    assert result.phase_metrics['MaxVSFpm'] == int(max_vs)
    assert result.phase_metrics['AvgVSFpm'] == int(avg_vs)        
    assert result.phase_metrics['LastMinuteMinVSFpm'] == int(last_min_min_vs)
    assert result.phase_metrics['LastMinuteMaxVSFpm'] == int(last_min_max_vs)
    assert result.phase_metrics['LastMinuteAvgVSFpm'] == int(last_min_avg_vs)

    issues_1000 = [i.value for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL]
    issues_2000 = [i.value for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL]

    issues_1000_str = "|".join(issues_1000)
    issues_2000_str = "|".join(issues_2000)
    assert issues_1000_str == one_thousand_issue
    assert issues_2000_str == two_thousand_issue