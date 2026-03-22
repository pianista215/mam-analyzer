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

def test_issue_low_vs_below_1000agl_by_vs(analyzer):
    """Issue triggers when VS < -1500 regardless of VSLast3Avg"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1600, AGLAltitude=900, VSLast3Avg=-1000),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-1600|900|-1500"


def test_issue_low_vs_below_1000agl_by_vs_last3_avg(analyzer):
    """Issue triggers when VSLast3Avg < -1150 even if VS > -1500"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1200, AGLAltitude=900, VSLast3Avg=-1200),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL)
    assert issue.value == "-1200|900|-1150"


def test_no_issue_when_vs_and_vs_last3_avg_within_limits(analyzer):
    """No issue when VS > -1500 and VSLast3Avg > -1150"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1200, AGLAltitude=900, VSLast3Avg=-1100),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)


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


def test_issue_vs_below_1000agl_glideslope_4deg_relaxed_threshold(analyzer):
    """With 4° glideslope, threshold relaxed to -1785: VS of -1600 no longer triggers"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1600, AGLAltitude=900),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=4.0)

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)


def test_issue_vs_below_1000agl_glideslope_4deg_still_triggers(analyzer):
    """With 4° glideslope, VS of -1800 still triggers with threshold -1785"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1800, AGLAltitude=900),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=4.0)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-1800|900|-1785"


def test_issue_vs_avg_below_1000agl_glideslope_4deg(analyzer):
    """With 4° glideslope, avg threshold relaxed to -1435"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1200, AGLAltitude=900, VSLast3Avg=-1450),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=4.0)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL)
    assert issue.value == "-1450|900|-1435"


def test_glideslope_at_exactly_3deg_uses_standard_thresholds(analyzer):
    """Glideslope exactly 3° applies no margin (threshold stays -1500)"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1600, AGLAltitude=900),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=3.0)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-1600|900|-1500"


# --- 5° glideslope: 200 intervals × 2.85 = 570 fpm margin → -2070 / -1720 ---

def test_glideslope_5deg_instant_below_threshold_triggers(analyzer):
    """5° glideslope: VS -2100 < -2070 triggers with threshold -2070"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2100, AGLAltitude=800),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=5.0)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-2100|800|-2070"


def test_glideslope_5deg_instant_above_threshold_no_issue(analyzer):
    """5° glideslope: VS -1800 > -2070 does not trigger"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1800, AGLAltitude=800),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=5.0)

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)


def test_glideslope_5deg_avg_below_threshold_triggers(analyzer):
    """5° glideslope: VSLast3Avg -1750 < -1720 triggers with threshold -1720"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=800, VSLast3Avg=-1750),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=5.0)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL)
    assert issue.value == "-1750|800|-1720"


def test_glideslope_5deg_avg_above_threshold_no_issue(analyzer):
    """5° glideslope: VSLast3Avg -1600 > -1720 does not trigger"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=800, VSLast3Avg=-1600),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=5.0)

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)


# --- 6.5° glideslope: 350 intervals × 2.85 = 997.5 → round → 998 fpm margin → -2498 / -2148 ---

def test_glideslope_6_5deg_instant_below_threshold_triggers(analyzer):
    """6.5° glideslope: VS -2500 < -2498 triggers with threshold -2498"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2500, AGLAltitude=700),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=6.5)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-2500|700|-2498"


def test_glideslope_6_5deg_instant_above_threshold_no_issue(analyzer):
    """6.5° glideslope: VS -2000 > -2498 does not trigger"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2000, AGLAltitude=700),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=6.5)

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)


def test_glideslope_6_5deg_avg_below_threshold_triggers(analyzer):
    """6.5° glideslope: VSLast3Avg -2200 < -2148 triggers with threshold -2148"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=700, VSLast3Avg=-2200),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=6.5)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL)
    assert issue.value == "-2200|700|-2148"


def test_glideslope_6_5deg_avg_above_threshold_no_issue(analyzer):
    """6.5° glideslope: VSLast3Avg -2000 > -2148 does not trigger"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=700, VSLast3Avg=-2000),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=6.5)

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)


def test_glideslope_6_5deg_rounding_boundary(analyzer):
    """6.5°: margin=round(997.5)=998, confirm VS exactly at threshold -2498 does NOT trigger"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2498, AGLAltitude=700),
    ]

    result = analyzer.analyze(events, start_time, end_time, glideslope_deg=6.5)

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)


@pytest.mark.parametrize("filename, app_start, app_end, min_vs, max_vs, avg_vs, last_min_min_vs, last_min_max_vs, last_min_avg_vs, glideslope_deg, one_thousand_issue, one_thousand_avg_issue, two_thousand_issue", [
    ("LEPA-LEPP-737.json", "2025-06-14T18:19:03.883981", "2025-06-14T18:22:03.883981", "-1903", "322", "-789", "-906", "-121", "-610", None, "-1903|999|-1500", "", ""),
    ("LEPP-LEMG-737.json", "2025-06-15T01:05:58.959306", "2025-06-15T01:08:58.959306", "-1045", "-219", "-791", "-976", "-219", "-626", None, "", "", ""),
    ("UHMA-PAOM-B350.json", "2025-06-16T00:04:26.575323", "2025-06-16T00:07:26.575323", "-994", "-44", "-605", "-994", "-44", "-539", None, "", "", ""),
    ("UHPT-UHMA-B350.json", "2025-06-15T19:58:00.819106", "2025-06-15T20:01:00.819106", "-775", "-279", "-594", "-775", "-279", "-616", None, "", "", ""),
    ("UHPT-UHMA-SF34.json", "2025-06-05T15:02:21.226652", "2025-06-05T15:05:21.226652", "-1355", "-109", "-670", "-1355", "-109", "-720", None, "", "", ""),
    ("UHSH-UHMM-B350.json", "2025-05-17T19:38:01.243375", "2025-05-17T19:41:01.24337", "-911", "-15", "-640", "-911", "-15", "-611", None, "", "", ""),
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-23T00:12:48.552044", "2025-06-23T00:15:48.552044", "-708", "59", "-479", "-658", "59", "-394", None, "", "", ""),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:04:23.315419", "2025-07-04T23:07:23.315419", "-1904", "795", "-402", "-899", "-256", "-537", None, "-1532|788|-1500|-1904|724|-1500", "", ""),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:44:13.316486", "-6534", "2898", "-208", "-1531", "-442", "-965", None, "-6534|744|-1500|-4571|519|-1500|-2355|794|-1500|-1750|918|-1500|-1650|832|-1500|-1545|430|-1500|-1600|380|-1500|-1531|497|-1500", "", "-4140|1136|-2205|1253"),
    ("short_flight_vslast3avg.json", "2026-02-04T08:33:54.5625775", "2026-02-04T08:36:54.5625775", "-1644", "1317", "-122", "-1076", "-269", "-748", None, "-1644|954|-1500", "-1294|906|-1150|-1209|888|-1150", ""),
    # glideslope 3.5° (threshold_instant=-1642, threshold_avg=-1292)
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:44:13.316486", "-6534", "2898", "-208", "-1531", "-442", "-965", 3.5, "-6534|744|-1642|-4571|519|-1642|-2355|794|-1642|-1750|918|-1642|-1650|832|-1642", "", "-4140|1136|-2205|1253"),
    ("short_flight_vslast3avg.json", "2026-02-04T08:33:54.5625775", "2026-02-04T08:36:54.5625775", "-1644", "1317", "-122", "-1076", "-269", "-748", 3.5, "-1644|954|-1642", "-1294|906|-1292", ""),
    # glideslope 4.0° (threshold_instant=-1785, threshold_avg=-1435)
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:44:13.316486", "-6534", "2898", "-208", "-1531", "-442", "-965", 4.0, "-6534|744|-1785|-4571|519|-1785|-2355|794|-1785", "", "-4140|1136|-2205|1253"),
    ("short_flight_vslast3avg.json", "2026-02-04T08:33:54.5625775", "2026-02-04T08:36:54.5625775", "-1644", "1317", "-122", "-1076", "-269", "-748", 4.0, "", "", ""),
])
def test_approach_analyzer_from_real_files(filename, app_start, app_end, min_vs, max_vs, avg_vs, last_min_min_vs, last_min_max_vs, last_min_avg_vs, glideslope_deg, one_thousand_issue, one_thousand_avg_issue, two_thousand_issue, analyzer):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = analyzer.analyze(events, parse_timestamp(app_start), parse_timestamp(app_end), glideslope_deg=glideslope_deg)

    assert result.phase_metrics['MinVSFpm'] == int(min_vs)
    assert result.phase_metrics['MaxVSFpm'] == int(max_vs)
    assert result.phase_metrics['AvgVSFpm'] == int(avg_vs)
    assert result.phase_metrics['LastMinuteMinVSFpm'] == int(last_min_min_vs)
    assert result.phase_metrics['LastMinuteMaxVSFpm'] == int(last_min_max_vs)
    assert result.phase_metrics['LastMinuteAvgVSFpm'] == int(last_min_avg_vs)

    issues_1000 = [i.value for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL]
    issues_1000_avg = [i.value for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL]
    issues_2000 = [i.value for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL]

    issues_1000_str = "|".join(issues_1000)
    issues_1000_avg_str = "|".join(issues_1000_avg)
    issues_2000_str = "|".join(issues_2000)
    assert issues_1000_str == one_thousand_issue
    assert issues_1000_avg_str == one_thousand_avg_issue
    assert issues_2000_str == two_thousand_issue
