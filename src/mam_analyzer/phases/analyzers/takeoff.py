from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.analyzer import Analyzer
from mam_analyzer.phases.analyzers.result import AnalysisResult
from mam_analyzer.utils.ground import event_has_on_ground, is_on_ground
from mam_analyzer.utils.landing import event_has_landing_vs_fpm, get_landing_vs_fpm_as_int
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.speed import event_has_ias, get_ias_as_int
from mam_analyzer.utils.units import haversine

class TakeoffAnalyzer(Analyzer):
    def analyze(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime
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

        result.phase_metrics["TakeoffBounces"] = bounces_vs
        result.phase_metrics["TakeoffGroundDistance"] = meters_until_airborne
        result.phase_metrics["TakeoffSpeed"] = airborne_speed

        return result









                


       
