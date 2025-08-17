from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.analyzer import Analyzer
from mam_analyzer.utils.altitude import event_has_altitude, get_altitude_as_int_rounded_to
from mam_analyzer.utils.filter import always_true
from mam_analyzer.utils.fuel import event_has_fuel, get_fuel_kg_as_float
from mam_analyzer.utils.search import find_first_index_backward, find_first_index_backward_starting_from_idx, find_first_index_forward, find_first_index_forward_starting_from_idx


class CruiseAnalyzer(Analyzer):
    def analyze(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime
    ) -> List[Tuple[str, str]]:
        """Analyze cruise phase generating:
           - fuel consumption
           - most common altitude flown
           - high altitude flown
        """

        #Calculate fuel consumption

        def get_fuel_consumption(events, start_idx, end_idx) -> int:
            found_start_fuel = find_first_index_forward_starting_from_idx(
                events,
                start_idx,
                event_has_fuel,
                None,
                None
            )

            if found_start_fuel is not None:
                _, start_fuel_event = found_start_fuel
                start_fuel = get_fuel_kg_as_float(start_fuel_event)
            else:
                raise RuntimeError("Can't retrieve start fuel event for cruise phase")

            found_end_fuel = find_first_index_backward_starting_from_idx(
                events,
                end_idx,
                event_has_fuel,
                None,
                None
            )

            if found_end_fuel is not None:
                _, start_end_event = found_end_fuel
                end_fuel = get_fuel_kg_as_float(start_end_event)
            else:
                raise RuntimeError("Can't retrieve end fuel event for cruise phase")

            fuel_consumption = round(start_fuel - end_fuel)
            return fuel_consumption


        def get_most_flown_altitude(events, start_idx, end_idx) -> Tuple[int, int]:
            if start_idx >= end_idx:
                return None

            altitudes_time = defaultdict(float)
            previous_alt = None
            previous_ts = None
            high_altitude = -1

            for i in range(start_idx, end_idx):
                event = events[i]

                if event_has_altitude(event):
                    alt = get_altitude_as_int_rounded_to(event, 500)

                    if alt > high_altitude:
                        high_altitude = alt

                    if previous_alt is None:
                        previous_alt = alt
                        previous_ts = event.timestamp
                    else:
                        if alt != previous_alt:
                            elapsed = (event.timestamp - previous_ts).total_seconds()
                            altitudes_time[previous_alt] += elapsed

                            previous_alt = alt
                            previous_ts = event.timestamp

            # Last batch
            if previous_alt is not None:
                elapsed = (events[end_idx-1].timestamp - previous_ts).total_seconds()
                altitudes_time[previous_alt] += elapsed

            if not altitudes_time:
                return None

            most_time_alt = max(altitudes_time.items(), key=lambda kv: kv[1])[0]

            return most_time_alt, high_altitude

        found_start_idx = find_first_index_forward(
            events,
            always_true,
            start_time,
            end_time,
        )

        if found_start_idx is None:
            raise RuntimeError("Cruise phase: can't determine valid start_idx")

        start_idx, _ = found_start_idx

        found_end_idx = find_first_index_backward(
            events,
            always_true,
            start_time,
            end_time,
        )

        if found_end_idx is None:
            raise RuntimeError("Cruise phase: can't determine valid end_idx")

        end_idx, _ = found_end_idx

        print("start %s end %s" % (start_idx, end_idx))

        fuel_consumption = get_fuel_consumption(events, start_idx, end_idx)
        result_altitudes = get_most_flown_altitude(events, start_idx, end_idx)
            
        if result_altitudes is None:
            raise RuntimeError("Can't retrieve most flown altitude or high altitude")

        most_time_alt, high_altitude = result_altitudes
        fuel_tuple = ("Fuel", fuel_consumption)
        most_tuple = ("CommonAlt", most_time_alt)
        high_tuple = ("HighAlt", high_altitude)

        return [fuel_tuple, most_tuple, high_tuple]









                


       