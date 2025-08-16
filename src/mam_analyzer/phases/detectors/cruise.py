from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.detector import Detector
from mam_analyzer.utils.search import find_first_index_backward_starting_from_idx, find_first_index_forward_starting_from_idx
from mam_analyzer.utils.units import heading_within_range

class CruiseDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        context: FlightDetectorContext,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect the cruise_phase: period the plane stays in the same altitude 
            with a range of variation allowed, but should be maintained along time
            from_time and to_time must be provided
            from_time -> takeoff_end and to_time -> app_start to avoid problems
        """

        if from_time is None or to_time is None:
            raise RuntimeError("TouchAndGoDetector must have from_time and to_time")

        # Step 1: Look for the highest altitude in this period of time
        high_altitude = 0
        high_altitude_agl = 0
        high_altitude_first_event_idx = None

        for idx in range(0,len(events)):
            e = events[idx]

            if e.timestamp >= from_time and e.timestamp <= to_time:

                e_altitude = e.other_changes.get("Altitude")
                if e_altitude is not None:
                    if int(e_altitude) > high_altitude:
                        high_altitude = int(e_altitude)
                        high_altitude_agl = int(e.other_changes.get("AGLAltitude"))
                        high_altitude_first_event_idx = idx

            elif e.timestamp > to_time:
                break

        # Step 2: Check is over 1500 AGL
        if high_altitude_first_event_idx is None or high_altitude_agl <= 1500:
            return None

        # Step 3: Get periods the altitude is maintained for enough time (5 minutes) with margin
        # Margin: 4000ft > 10000ft, 2000ft > 7000ft, 1000ft otherwise
        if high_altitude_agl > 10000:
            margin_altitude = 4000
        elif high_altitude_agl > 7000:
            margin_altitude = 2000
        else:
            margin_altitude = 1000

        print(f"Margin altitude {margin_altitude} for high {high_altitude} (AGL {high_altitude_agl})")

        # Look backwards and forward from the event to see when starts and ends
        def outOfCruise(e: FlightEvent) -> bool:
            e_alt = e.other_changes.get("Altitude")
            return e_alt is not None and abs(high_altitude - int(e_alt)) > margin_altitude

        found_start = find_first_index_backward_starting_from_idx(
            events,
            high_altitude_first_event_idx,
            outOfCruise,
            from_time,
            to_time
        )

        found_end = find_first_index_forward_starting_from_idx(
            events,
            high_altitude_first_event_idx,
            outOfCruise,
            from_time,
            to_time
        )

        start_cruise_time = from_time
        end_cruise_time = to_time

        if found_start is not None:
            start_idx, _ = found_start
            start_cruise_time = events[start_idx + 1].timestamp

        if found_end is not None:
            end_idx, _ = found_end
            end_cruise_time = events[end_idx - 1].timestamp

        diff = end_cruise_time - start_cruise_time

        if diff > timedelta(minutes = 7):
            return start_cruise_time, end_cruise_time
        else:
            return None


                


       