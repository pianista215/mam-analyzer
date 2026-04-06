from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.approach import ApproachAnalyzer, PARAM_GLIDESLOPE_DEG, PARAM_GLIDESLOPE_DEG
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
    """Issue triggers when VS < -2000 in the 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2100, AGLAltitude=900, VSLast3Avg=-1000),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-2100|900|-2000"


def test_issue_low_vs_below_1000agl_by_vs_last3_avg(analyzer):
    """Issue triggers when VSLast3Avg < -1650 and VS > -2000 in the 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1200, AGLAltitude=900, VSLast3Avg=-1700),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL)
    assert issue.value == "-1700|900|-1650"


def test_no_issue_when_vs_and_vs_last3_avg_within_limits(analyzer):
    """No issue when VS > -2000 and VSLast3Avg > -1650 in the 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1900, AGLAltitude=900, VSLast3Avg=-1600),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)


def test_issue_low_vs_below_500agl_by_vs(analyzer):
    """Issue triggers when VS < -1500 below 500 AGL"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1600, AGLAltitude=400, VSLast3Avg=-1000),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL)
    assert issue.value == "-1600|400|-1500"


def test_issue_low_vs_below_500agl_by_vs_last3_avg(analyzer):
    """Issue triggers when VSLast3Avg < -1150 and VS > -1500 below 500 AGL"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1200, AGLAltitude=400, VSLast3Avg=-1200),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL)
    assert issue.value == "-1200|400|-1150"


def test_no_issue_below_500agl_within_limits(analyzer):
    """No issue when VS > -1500 and VSLast3Avg > -1150 below 500 AGL"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1200, AGLAltitude=400, VSLast3Avg=-1100),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL for i in result.issues)
    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL for i in result.issues)


def test_500agl_vs_triggers_not_avg(analyzer):
    """When VS < -1500 below 500 AGL, only instant issue raised (avg not evaluated)"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1600, AGLAltitude=400, VSLast3Avg=-1200),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL for i in result.issues)
    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL for i in result.issues)


def test_issue_low_vs_below_2000agl(analyzer):
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=20), VSFpm=-2500, AGLAltitude=1500),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL)
    assert issue.value == "-2500|1500|-2000"


def test_issue_vs_below_1000agl_glideslope_4deg_relaxed_threshold(analyzer):
    """With 4° glideslope, 500-1000 AGL threshold relaxed to -2285: VS of -2100 no longer triggers"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2100, AGLAltitude=900),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 4.0})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)


def test_issue_vs_below_1000agl_glideslope_4deg_still_triggers(analyzer):
    """With 4° glideslope, VS of -2300 still triggers in 500-1000 AGL band with threshold -2285"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2300, AGLAltitude=900),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 4.0})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-2300|900|-2285"


def test_issue_vs_avg_below_1000agl_glideslope_4deg(analyzer):
    """With 4° glideslope, avg threshold for 500-1000 AGL band relaxed to -1935"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1200, AGLAltitude=900, VSLast3Avg=-2000),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 4.0})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL)
    assert issue.value == "-2000|900|-1935"


def test_glideslope_at_exactly_3deg_uses_standard_thresholds(analyzer):
    """Glideslope exactly 3° applies no margin (500-1000 AGL threshold stays -2000)"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2100, AGLAltitude=900),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 3.0})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-2100|900|-2000"


# --- 5° glideslope: 200 intervals × 2.85 = 570 fpm margin → instant_500=-2070 / avg_500=-1720 / threshold_2000=-2570 / avg_1000=-2220 ---

def test_glideslope_5deg_instant_below_1000_threshold_triggers(analyzer):
    """5° glideslope: VS -2600 < -2570 triggers in 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2600, AGLAltitude=800),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 5.0})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-2600|800|-2570"


def test_glideslope_5deg_instant_above_1000_threshold_no_issue(analyzer):
    """5° glideslope: VS -2100 > -2570 does not trigger in 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2100, AGLAltitude=800),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 5.0})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)


def test_glideslope_5deg_avg_below_1000_threshold_triggers(analyzer):
    """5° glideslope: VSLast3Avg -2250 < -2220 triggers in 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=800, VSLast3Avg=-2250),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 5.0})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL)
    assert issue.value == "-2250|800|-2220"


def test_glideslope_5deg_avg_above_1000_threshold_no_issue(analyzer):
    """5° glideslope: VSLast3Avg -2100 > -2220 does not trigger in 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=800, VSLast3Avg=-2100),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 5.0})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)


def test_glideslope_5deg_instant_below_500_threshold_triggers(analyzer):
    """5° glideslope: VS -2100 < -2070 triggers in <500 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2100, AGLAltitude=400),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 5.0})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL)
    assert issue.value == "-2100|400|-2070"


def test_glideslope_5deg_instant_above_500_threshold_no_issue(analyzer):
    """5° glideslope: VS -1800 > -2070 does not trigger in <500 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1800, AGLAltitude=400),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 5.0})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL for i in result.issues)


def test_glideslope_5deg_avg_below_500_threshold_triggers(analyzer):
    """5° glideslope: VSLast3Avg -1750 < -1720 triggers in <500 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=400, VSLast3Avg=-1750),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 5.0})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL)
    assert issue.value == "-1750|400|-1720"


def test_glideslope_5deg_avg_above_500_threshold_no_issue(analyzer):
    """5° glideslope: VSLast3Avg -1600 > -1720 does not trigger in <500 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=400, VSLast3Avg=-1600),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 5.0})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL for i in result.issues)


# --- 6.5° glideslope: 350 intervals × 2.85 = 997.5 → round → 998 fpm margin → instant_500=-2498 / avg_500=-2148 / threshold_2000=-2998 / avg_1000=-2648 ---

def test_glideslope_6_5deg_instant_below_1000_threshold_triggers(analyzer):
    """6.5° glideslope: VS -3000 < -2998 triggers in 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-3000, AGLAltitude=700),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 6.5})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL)
    assert issue.value == "-3000|700|-2998"


def test_glideslope_6_5deg_instant_above_1000_threshold_no_issue(analyzer):
    """6.5° glideslope: VS -2000 > -2998 does not trigger in 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2000, AGLAltitude=700),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 6.5})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)


def test_glideslope_6_5deg_avg_below_1000_threshold_triggers(analyzer):
    """6.5° glideslope: VSLast3Avg -2700 < -2648 triggers in 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=700, VSLast3Avg=-2700),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 6.5})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL)
    assert issue.value == "-2700|700|-2648"


def test_glideslope_6_5deg_avg_above_1000_threshold_no_issue(analyzer):
    """6.5° glideslope: VSLast3Avg -2000 > -2648 does not trigger in 500-1000 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=700, VSLast3Avg=-2000),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 6.5})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL for i in result.issues)


def test_glideslope_6_5deg_instant_below_500_threshold_triggers(analyzer):
    """6.5° glideslope: VS -2500 < -2498 triggers in <500 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2500, AGLAltitude=400),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 6.5})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL)
    assert issue.value == "-2500|400|-2498"


def test_glideslope_6_5deg_instant_above_500_threshold_no_issue(analyzer):
    """6.5° glideslope: VS -2000 > -2498 does not trigger in <500 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2000, AGLAltitude=400),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 6.5})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL for i in result.issues)


def test_glideslope_6_5deg_avg_below_500_threshold_triggers(analyzer):
    """6.5° glideslope: VSLast3Avg -2200 < -2148 triggers in <500 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=400, VSLast3Avg=-2200),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 6.5})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL)
    assert issue.value == "-2200|400|-2148"


def test_glideslope_6_5deg_avg_above_500_threshold_no_issue(analyzer):
    """6.5° glideslope: VSLast3Avg -2000 > -2148 does not trigger in <500 AGL band"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-1500, AGLAltitude=400, VSLast3Avg=-2000),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 6.5})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL for i in result.issues)


def test_glideslope_6_5deg_rounding_boundary(analyzer):
    """6.5°: margin=round(997.5)=998; VS exactly at threshold -2998 in 500-1000 AGL band does NOT trigger"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2998, AGLAltitude=700),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 6.5})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL for i in result.issues)


# --- 2000 AGL issue: same margin applied to -2000 base threshold ---

def test_issue_2000agl_standard_threshold(analyzer):
    """No glideslope: threshold stays at -2000"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2100, AGLAltitude=1500),
    ]

    result = analyzer.analyze(events, start_time, end_time)

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL)
    assert issue.value == "-2100|1500|-2000"


def test_issue_2000agl_glideslope_5deg_relaxed_threshold(analyzer):
    """5° glideslope: threshold relaxed to -2570; VS -2100 no longer triggers"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2100, AGLAltitude=1500),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 5.0})

    assert not any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL for i in result.issues)


def test_issue_2000agl_glideslope_5deg_still_triggers(analyzer):
    """5° glideslope: VS -2600 < -2570 still triggers"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2600, AGLAltitude=1500),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 5.0})

    assert any(i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL for i in result.issues)
    issue = next(i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL)
    assert issue.value == "-2600|1500|-2570"


def test_issue_2000agl_glideslope_6_5deg(analyzer):
    """6.5° glideslope: threshold -2998; VS -2500 does not trigger, -3000 does"""
    start_time = datetime(2025, 1, 1, 12, 0, 0)
    end_time = start_time + timedelta(minutes=1)

    events = [
        make_event(start_time + timedelta(seconds=10), VSFpm=-2500, AGLAltitude=1500),
        make_event(start_time + timedelta(seconds=20), VSFpm=-3000, AGLAltitude=1400),
    ]

    result = analyzer.analyze(events, start_time, end_time, phase_params={PARAM_GLIDESLOPE_DEG: 6.5})

    issues_2000 = [i for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL]
    assert len(issues_2000) == 1
    assert issues_2000[0].value == "-3000|1400|-2998"


# Parametrized thresholds reference:
# std (no gs):  instant_500=-1500, avg_500=-1150, threshold_2000=-2000, avg_1000=-1650
# gs=3.5°:      margin=142 → instant_500=-1642, avg_500=-1292, threshold_2000=-2142, avg_1000=-1792
# gs=4.0°:      margin=285 → instant_500=-1785, avg_500=-1435, threshold_2000=-2285, avg_1000=-1935
# gs=5.0°:      margin=570 → instant_500=-2070, avg_500=-1720, threshold_2000=-2570, avg_1000=-2220
# gs=6.5°:      margin=998 → instant_500=-2498, avg_500=-2148, threshold_2000=-2998, avg_1000=-2648
@pytest.mark.parametrize("filename, app_start, app_end, min_vs, max_vs, avg_vs, last_min_min_vs, last_min_max_vs, last_min_avg_vs, glideslope_deg, one_thousand_issue, one_thousand_avg_issue, two_thousand_issue, five_hundred_issue, five_hundred_avg_issue", [
    ("LEPA-LEPP-737.json", "2025-06-14T18:19:03.883981", "2025-06-14T18:22:03.883981", "-1903", "322", "-789", "-906", "-121", "-610", None, "", "", "", "", ""),
    ("LEPP-LEMG-737.json", "2025-06-15T01:05:58.959306", "2025-06-15T01:08:58.959306", "-1045", "-219", "-791", "-976", "-219", "-626", None, "", "", "", "", ""),
    ("UHMA-PAOM-B350.json", "2025-06-16T00:04:26.575323", "2025-06-16T00:07:26.575323", "-994", "-44", "-605", "-994", "-44", "-539", None, "", "", "", "", ""),
    ("UHPT-UHMA-B350.json", "2025-06-15T19:58:00.819106", "2025-06-15T20:01:00.819106", "-775", "-279", "-594", "-775", "-279", "-616", None, "", "", "", "", ""),
    ("UHPT-UHMA-SF34.json", "2025-06-05T15:02:21.226652", "2025-06-05T15:05:21.226652", "-1355", "-109", "-670", "-1355", "-109", "-720", None, "", "", "", "", ""),
    ("UHSH-UHMM-B350.json", "2025-05-17T19:38:01.243375", "2025-05-17T19:41:01.24337", "-911", "-15", "-640", "-911", "-15", "-611", None, "", "", "", "", ""),
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-23T00:12:48.552044", "2025-06-23T00:15:48.552044", "-708", "59", "-479", "-658", "59", "-394", None, "", "", "", "", ""),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:04:23.315419", "2025-07-04T23:07:23.315419", "-1904", "795", "-402", "-899", "-256", "-537", None, "", "", "", "", ""),
    # LEBB second approach: AGL 744/519/794 in 500-1000 band (< -2000), AGL 430/380/497 in <500 band (< -1500)
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:44:13.316486", "-6534", "2898", "-208", "-1531", "-442", "-965", None, "-6534|744|-2000|-4571|519|-2000|-2355|794|-2000", "", "-4140|1136|-2000|-2205|1253|-2000", "-1545|430|-1500|-1600|380|-1500|-1531|497|-1500", ""),
    ("short_flight_vslast3avg.json", "2026-02-04T08:33:54.5625775", "2026-02-04T08:36:54.5625775", "-1644", "1317", "-122", "-1076", "-269", "-748", None, "", "", "", "", ""),
    # glideslope 3.5° (instant_500=-1642, avg_500=-1292, threshold_2000=-2142, avg_1000=-1792)
    # AGL 744/519/794 in 500-1000 (< -2142). AGL 430/380/497 in <500: -1545/-1600/-1531 > -1642, no trigger.
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:44:13.316486", "-6534", "2898", "-208", "-1531", "-442", "-965", 3.5, "-6534|744|-2142|-4571|519|-2142|-2355|794|-2142", "", "-4140|1136|-2142|-2205|1253|-2142", "", ""),
    ("short_flight_vslast3avg.json", "2026-02-04T08:33:54.5625775", "2026-02-04T08:36:54.5625775", "-1644", "1317", "-122", "-1076", "-269", "-748", 3.5, "", "", "", "", ""),
    # glideslope 4.0° (instant_500=-1785, avg_500=-1435, threshold_2000=-2285, avg_1000=-1935)
    # AGL 744/519/794 in 500-1000 (< -2285). AGL 430/380/497 in <500: all > -1785, no trigger.
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:44:13.316486", "-6534", "2898", "-208", "-1531", "-442", "-965", 4.0, "-6534|744|-2285|-4571|519|-2285|-2355|794|-2285", "", "-4140|1136|-2285", "", ""),
    ("short_flight_vslast3avg.json", "2026-02-04T08:33:54.5625775", "2026-02-04T08:36:54.5625775", "-1644", "1317", "-122", "-1076", "-269", "-748", 4.0, "", "", "", "", ""),
    # glideslope 5.0° (instant_500=-2070, avg_500=-1720, threshold_2000=-2570, avg_1000=-2220)
    # AGL 744/519 in 500-1000 (< -2570); AGL 794 at -2355 > -2570. AGL 430/380/497: all > -2070, no trigger.
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:44:13.316486", "-6534", "2898", "-208", "-1531", "-442", "-965", 5.0, "-6534|744|-2570|-4571|519|-2570", "", "-4140|1136|-2570", "", ""),
    # glideslope 6.5° (instant_500=-2498, avg_500=-2148, threshold_2000=-2998, avg_1000=-2648)
    # AGL 744/519 in 500-1000 (< -2998). AGL 430/380/497: all > -2498, no trigger.
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:44:13.316486", "-6534", "2898", "-208", "-1531", "-442", "-965", 6.5, "-6534|744|-2998|-4571|519|-2998", "", "-4140|1136|-2998", "", ""),
])
def test_approach_analyzer_from_real_files(filename, app_start, app_end, min_vs, max_vs, avg_vs, last_min_min_vs, last_min_max_vs, last_min_avg_vs, glideslope_deg, one_thousand_issue, one_thousand_avg_issue, two_thousand_issue, five_hundred_issue, five_hundred_avg_issue, analyzer):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = analyzer.analyze(events, parse_timestamp(app_start), parse_timestamp(app_end), phase_params={PARAM_GLIDESLOPE_DEG: glideslope_deg} if glideslope_deg is not None else None)

    assert result.phase_metrics['MinVSFpm'] == int(min_vs)
    assert result.phase_metrics['MaxVSFpm'] == int(max_vs)
    assert result.phase_metrics['AvgVSFpm'] == int(avg_vs)
    assert result.phase_metrics['LastMinuteMinVSFpm'] == int(last_min_min_vs)
    assert result.phase_metrics['LastMinuteMaxVSFpm'] == int(last_min_max_vs)
    assert result.phase_metrics['LastMinuteAvgVSFpm'] == int(last_min_avg_vs)

    issues_1000 = [i.value for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL]
    issues_1000_avg = [i.value for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL]
    issues_2000 = [i.value for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL]
    issues_500 = [i.value for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_BELOW_500AGL]
    issues_500_avg = [i.value for i in result.issues if i.code == Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_500AGL]

    assert "|".join(issues_1000) == one_thousand_issue
    assert "|".join(issues_1000_avg) == one_thousand_avg_issue
    assert "|".join(issues_2000) == two_thousand_issue
    assert "|".join(issues_500) == five_hundred_issue
    assert "|".join(issues_500_avg) == five_hundred_avg_issue
