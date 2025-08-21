from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.analyzer import Analyzer
from mam_analyzer.utils.ground import event_has_on_ground, is_on_ground
from mam_analyzer.utils.landing import event_has_landing_vs_fpm, get_landing_vs_fpm_as_int
from mam_analyzer.utils.units import haversine

class TouchAndGoAnalyzer(Analyzer):
    def analyze(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Analyze touch phase generating:
           - number of bounces
           - meters traveled until we are back in the sky
        """

        landing_vs_fpm = None
        bounces_vs = []

        # Consider distance from first point (landing) until the point we are back in the sky
        # We are not considering intermediate changes to calculate it easier
        touch_lat = None
        touch_lon = None
        meters_until_airborne = None

        for e in events:
            ts = e.timestamp
            if ts >= start_time:
                if ts <= end_time:
                    if event_has_landing_vs_fpm(e):
                        fpm = get_landing_vs_fpm_as_int(e)

                        if landing_vs_fpm is None:
                            landing_vs_fpm = fpm
                            # Landing events have all information
                            touch_lat = e.latitude
                            touch_lon = e.longitude
                        else:
                            bounces_vs.append(fpm)
                            meters_until_airborne = None

                    if (
                        touch_lat is not None
                        and touch_lon is not None
                        and meters_until_airborne is None
                        and event_has_on_ground(e)
                        and not is_on_ground(e)
                    ):
                        airborne_lat = e.latitude
                        airborne_lon = e.longitude

                        meters_until_airborne = round(
                            haversine(touch_lat, touch_lon, airborne_lat, airborne_lon)
                        )

                else:
                    break
            
        if landing_vs_fpm is None:
            raise RuntimeError("Can't find touchdown from touch & go phase")

        result = {}

        result["TouchGoVSFpm"] = landing_vs_fpm
        result["TouchGoBounces"] = bounces_vs
        result["TouchGoGroundDistance"] = meters_until_airborne

        return result









                


       