from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from mam_analyzer.models.flight_context import FlightContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.analyzer import Analyzer
from mam_analyzer.phases.analyzers.result import AnalysisResult
from mam_analyzer.utils.ground import event_has_on_ground, is_on_ground
from mam_analyzer.utils.landing import event_has_landing_vs_fpm, get_landing_vs_fpm_as_int
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.runway import match_runway_end
from mam_analyzer.utils.speed import event_has_ias, get_ias_as_int
from mam_analyzer.utils.units import haversine

class TakeoffAnalyzer(Analyzer):

    METRIC_TAKEOFF_BOUNCES = "TakeoffBounces"
    METRIC_TAKEOFF_GROUND_DISTANCE = "TakeoffGroundDistance"
    METRIC_TAKEOFF_SPEED = "TakeoffSpeed"
    METRIC_TAKEOFF_RUNWAY = "TakeoffRunway"
    METRIC_TAKEOFF_RUNWAY_REMAINING_PCT = "TakeoffRunwayRemainingPct"

    def analyze(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime,
        context: Optional[FlightContext] = None,
    ) -> AnalysisResult:
        """Analyze takeoff phase generating:
           - number of bounces
           - takeoff speed 
           - meters traveled until airborne
        """

        bounces_vs = []

        # Consider distance from the start of takeoff until the point we are airborne
        # We are not considering intermediate changes to calculate it easier
        run_start_lat = None
        run_start_lon = None
        meters_until_airborne = None
        airborne_speed = None

        for e in events:
            ts = e.timestamp
            if ts >= start_time:
                if ts <= end_time:

                    if run_start_lat is None and run_start_lon is None:
                        if event_has_location(e):
                            run_start_lat = e.latitude
                            run_start_lon = e.longitude

                    if event_has_landing_vs_fpm(e):
                        fpm = get_landing_vs_fpm_as_int(e)
                        bounces_vs.append(fpm)
                        # Reset the flags because takeoff is not completed
                        meters_until_airborne = None
                        airborne_speed = None

                    if (
                        run_start_lat is not None
                        and run_start_lon is not None
                        and meters_until_airborne is None
                        and event_has_on_ground(e)
                        and not is_on_ground(e)
                    ):
                        airborne_lat = e.latitude
                        airborne_lon = e.longitude
                        meters_until_airborne = round(
                            haversine(run_start_lat, run_start_lon, airborne_lat, airborne_lon)
                        )

                        if not event_has_ias(e):
                            raise RuntimeError("Event marking airborne must include IAS")

                        airborne_speed = get_ias_as_int(e)

                else:
                    break
            
        if meters_until_airborne is None or airborne_speed is None:
            raise RuntimeError("Can't get meters and speed for takeoff phase")

        result = AnalysisResult()

        result.phase_metrics[self.METRIC_TAKEOFF_BOUNCES] = bounces_vs
        result.phase_metrics[self.METRIC_TAKEOFF_GROUND_DISTANCE] = meters_until_airborne
        result.phase_metrics[self.METRIC_TAKEOFF_SPEED] = airborne_speed

        # Runway identification
        if (
            context is not None
            and context.departure is not None
            and context.departure.runways
            and airborne_lat is not None
            and airborne_lon is not None
        ):
            airborne_heading = None
            for e in events:
                ts = e.timestamp
                if ts >= start_time and ts <= end_time:
                    if event_has_on_ground(e) and not is_on_ground(e) and e.heading is not None:
                        airborne_heading = e.heading
                        break

            if airborne_heading is not None:
                rwy_match = match_runway_end(
                    context.departure, airborne_heading, airborne_lat, airborne_lon
                )
                if rwy_match is not None:
                    rwy, matched_end = rwy_match
                    result.phase_metrics[self.METRIC_TAKEOFF_RUNWAY] = matched_end.designator

                    # Find the opposite end (the one the aircraft is flying towards)
                    opposite_end = rwy.ends[1] if matched_end is rwy.ends[0] else rwy.ends[0]
                    remaining_m = haversine(
                        airborne_lat, airborne_lon,
                        opposite_end.latitude, opposite_end.longitude,
                    )
                    remaining_pct = round(remaining_m / rwy.length_m * 100)
                    result.phase_metrics[self.METRIC_TAKEOFF_RUNWAY_REMAINING_PCT] = remaining_pct

        return result