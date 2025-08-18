from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.analyzer import Analyzer
from mam_analyzer.utils.vertical_speed import event_has_vertical_speed, get_vertical_speed_as_int

class ApproachAnalyzer(Analyzer):
    def analyze(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime
    ) -> List[Tuple[str, str]]:
        """Analyze approach phase generating:
           - average vertical speed fpm
           - min vertical speed
           - max vertical speed
        """

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

        min_tuple = ("MinVSFpm", min_vs)
        max_tuple = ("MaxVSFpm", max_vs)
        avg = round(vs_sum/vs_found)
        avg_tuple = ("AvgVSFpm", avg)

        last_min_tuple = ("LastMinuteMinVSFpm", last_minute_min_vs)
        last_max_tuple = ("LastMinuteMaxVSFpm", last_minute_max_vs)
        last_min_avg = round(last_minute_vs_sum/last_minute_vs_found)
        last_min_avg_tuple = ("LastMinuteAvgVSFpm", last_min_avg)

        return [min_tuple, max_tuple, avg_tuple, last_min_tuple, last_max_tuple, last_min_avg_tuple]









                


       