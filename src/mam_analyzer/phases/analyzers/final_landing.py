from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.analyzer import Analyzer
from mam_analyzer.phases.analyzers.issues import Issues
from mam_analyzer.phases.analyzers.result import AnalysisResult,AnalysisIssue
from mam_analyzer.utils.engines import all_engines_are_off, some_engine_is_off
from mam_analyzer.utils.landing import event_has_landing_vs_fpm, get_landing_vs_fpm_as_int
from mam_analyzer.utils.speed import event_has_ias, get_ias_as_int
from mam_analyzer.utils.units import haversine

class FinalLandingAnalyzer(Analyzer):

    METRIC_LANDING_FPM = "LandingVSFpm"
    METRIC_BOUNCES = "LandingBounces"
    METRIC_BRAKE_DISTANCE = "BrakeDistance"

    def analyze(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime
    ) -> AnalysisResult:
        """Analyze final landing phase generating:
           - number of bounces
           - meters traveled until brake below 40knots
        """

        result = AnalysisResult()

        landing_vs_fpm = None
        bounces_vs = []

        # Consider distance from first point (landing) until the point we are below 40 knots
        # We are not considering intermediate changes to calculate it easier
        touch_lat = None
        touch_lon = None
        meters_until_brake = None

        for e in events:
            ts = e.timestamp
            if ts >= start_time:
                if ts <= end_time:
                    if event_has_landing_vs_fpm(e):
                        fpm = get_landing_vs_fpm_as_int(e)

                        if fpm < -700:
                            result.issues.append(
                                AnalysisIssue(
                                    code=Issues.ISSUE_HARD_LANDING_FPM,
                                    timestamp=e.timestamp,
                                    value=fpm
                                )
                            )

                        if landing_vs_fpm is None:
                            landing_vs_fpm = fpm
                            # Landing events have all information
                            touch_lat = e.latitude
                            touch_lon = e.longitude
                            #Check only in main touchdown for engine failures
                            if all_engines_are_off(e):
                                result.issues.append(
                                    AnalysisIssue(
                                        code=Issues.ISSUE_LANDING_WITHOUT_ENGINES,
                                        timestamp=e.timestamp,
                                    )
                                ) 
                            elif some_engine_is_off(e):
                                result.issues.append(
                                    AnalysisIssue(
                                        code=Issues.ISSUE_LANDING_WITH_SOME_ENGINE_STOPPED,
                                        timestamp=e.timestamp,
                                    )
                                )
                        else:
                            bounces_vs.append(fpm)

                    if (
                        touch_lat is not None
                        and touch_lon is not None
                        and event_has_ias(e)
                        and get_ias_as_int(e) < 40
                    ):
                        break_lat = e.latitude
                        break_lon = e.longitude

                        meters_until_brake = round(
                            haversine(touch_lat, touch_lon, break_lat, break_lon)
                        )

                        break

                else:
                    break
            
        if landing_vs_fpm is None:
            raise RuntimeError("Can't find touchdown from landing phase")        

        result.phase_metrics[self.METRIC_LANDING_FPM] = landing_vs_fpm
        result.phase_metrics[self.METRIC_BOUNCES] = bounces_vs
        result.phase_metrics[self.METRIC_BRAKE_DISTANCE] = meters_until_brake

        return result