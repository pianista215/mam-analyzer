from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from mam_analyzer.models.flight_context import FlightContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.analyzer import Analyzer
from mam_analyzer.phases.analyzers.issues import Issues
from mam_analyzer.phases.analyzers.result import AnalysisResult, AnalysisIssue
from mam_analyzer.utils.altitude import event_has_agl_altitude, get_agl_altitude_as_int
from mam_analyzer.utils.vertical_speed import (
    event_has_vertical_speed,
    get_vertical_speed_as_int,
    event_has_vs_last3_avg,
    get_vs_last3_avg_as_int,
)

PARAM_GLIDESLOPE_DEG = "glideslope_deg"

_BASE_INSTANT = -1500
_BASE_AVG = -1150
_BASE_2000 = -2000
_GLIDESLOPE_BASE_DEG = 3.0
_FPM_PER_HUNDREDTH_DEG = 2.85  # fpm added per 0.01° above _GLIDESLOPE_BASE_DEG


def _get_thresholds(glideslope_deg: Optional[float]):
    margin = 0
    if glideslope_deg is not None and glideslope_deg > _GLIDESLOPE_BASE_DEG:
        margin = round((glideslope_deg - _GLIDESLOPE_BASE_DEG) * 100 * _FPM_PER_HUNDREDTH_DEG)
    return _BASE_INSTANT - margin, _BASE_AVG - margin, _BASE_2000 - margin


class ApproachAnalyzer(Analyzer):
    def analyze(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime,
        context: Optional[FlightContext] = None,
        phase_params: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        """Analyze approach phase generating:
           - average vertical speed fpm
           - min vertical speed
           - max vertical speed
           Issues:
           - VS < threshold_2000 fpm below 2000AGL (default -2000, relaxed for steep approaches)
           - VS < threshold_instant fpm below 1000AGL (default -1500, relaxed for steep approaches)
           - VSLast3Avg < threshold_avg fpm below 1000AGL (default -1150, relaxed for steep approaches)
        """

        result = AnalysisResult()

        glideslope_deg = (phase_params or {}).get(PARAM_GLIDESLOPE_DEG)
        threshold_instant, threshold_avg, threshold_2000 = _get_thresholds(glideslope_deg)

        last_min_start = end_time + timedelta(seconds=-60)

        min_vs = None
        max_vs = None
        vs_found = 0
        vs_sum = 0

        last_minute_min_vs = None
        last_minute_max_vs = None
        last_minute_vs_found = 0
        last_minute_vs_sum = 0

        for e in events:
            ts = e.timestamp
            if ts >= start_time:
                if ts < end_time:
                    if event_has_vertical_speed(e):
                        vs = get_vertical_speed_as_int(e)

                        #Issues
                        if event_has_agl_altitude(e):
                            agl = get_agl_altitude_as_int(e)

                            if agl < 1000:
                                if vs < threshold_instant:
                                    result.issues.append(
                                        AnalysisIssue(
                                            code=Issues.ISSUE_APP_HIGH_VS_BELOW_1000AGL,
                                            timestamp=e.timestamp,
                                            value=f"{vs}|{agl}|{threshold_instant}"
                                        )
                                    )
                                elif event_has_vs_last3_avg(e) and get_vs_last3_avg_as_int(e) < threshold_avg:
                                    result.issues.append(
                                        AnalysisIssue(
                                            code=Issues.ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL,
                                            timestamp=e.timestamp,
                                            value=f"{get_vs_last3_avg_as_int(e)}|{agl}|{threshold_avg}"
                                        )
                                    )
                            elif agl < 2000 and vs < threshold_2000:
                                result.issues.append(
                                    AnalysisIssue(
                                        code=Issues.ISSUE_APP_HIGH_VS_BELOW_2000AGL,
                                        timestamp=e.timestamp,
                                        value=f"{vs}|{agl}|{threshold_2000}"
                                    )
                                )

                        #Stats
                        vs_sum += vs
                        vs_found += 1

                        if min_vs is None or vs < min_vs:
                            min_vs = vs
                        if max_vs is None or vs > max_vs:
                            max_vs = vs

                        if ts >= last_min_start:
                            last_minute_vs_sum += vs
                            last_minute_vs_found += 1

                            if last_minute_min_vs is None or vs < last_minute_min_vs:
                                last_minute_min_vs = vs
                            if last_minute_max_vs is None or vs > last_minute_max_vs:
                                last_minute_max_vs = vs

                else:
                    break

        if vs_found == 0:
            raise RuntimeError("Can't retrieve vertical speed from approach phase")

        if last_minute_vs_found == 0:
            raise RuntimeError("Can't retrieve vertical speed from approach phase last minute")

        result.phase_metrics["MinVSFpm"] = min_vs
        result.phase_metrics["MaxVSFpm"] = max_vs

        avg = round(vs_sum/vs_found)
        result.phase_metrics["AvgVSFpm"] = avg

        result.phase_metrics["LastMinuteMinVSFpm"] = last_minute_min_vs
        result.phase_metrics["LastMinuteMaxVSFpm"] = last_minute_max_vs

        last_min_avg = round(last_minute_vs_sum/last_minute_vs_found)
        result.phase_metrics["LastMinuteAvgVSFpm"] = last_min_avg

        return result
