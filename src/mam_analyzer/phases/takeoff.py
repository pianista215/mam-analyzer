from datetime import datetime,timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.detector import Detector
from mam_analyzer.utils.search import find_first_index_forward,find_first_index_backward_starting_from_idx
from mam_analyzer.utils.units import heading_within_range

class TakeoffDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        context: FlightDetectorContext,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect the first takeoff: from the start of takeoff run until flaps 0, gear up or 1 minute."""
        airborne_idx = None
        airborne_heading = None
        takeoff_start = None
        takeoff_end = None
        flaps_at_takeoff = None

        # TODO: RETURN EVENTS INSTEAD OF TIMESTAMP?
        # TODO: USE ACCELERATION INSTEAD OF HEADING?

        # Step 1: First event on air (onGround=False)
        def onAirCondition(e: FlightEvent)->bool:
            return e.on_ground is False

        found_airborne = find_first_index_forward(
            events, 
            onAirCondition, 
            from_time, 
            to_time
        )

        if found_airborne is None:
            return None  # Takeoff not detected 
        else:
            airborne_idx, airborne_event = found_airborne
            airborne_heading = airborne_event.heading
            flaps_at_takeoff = airborne_event.flaps      
        

        # Step 2: Look backward for first event with heading out of range
        def headingIsOutOfRange(e: FlightEvent)->bool:
            print(f"{e.heading} vs {airborne_heading}")
            return (
                e.heading is not None
                and not heading_within_range(e.heading, airborne_heading)
            )


        found_diff_heading = find_first_index_backward_starting_from_idx(
            events,
            airborne_idx - 1,
            headingIsOutOfRange,
            from_time,
            to_time
        )

        if found_diff_heading is None:
            # If all previous events are in correct heading use first event
            takeoff_start = events[0].timestamp
        else:
            diff_heading_idx, _ = found_diff_heading
            takeoff_start = events[diff_heading_idx + 1].timestamp
            
        # Step 3: Look for the end of the takeoff phase from airbone_idx
        deadline = events[airborne_idx].timestamp + timedelta(minutes=1)

        for event in events[airborne_idx + 1:]:
            ts = event.timestamp

            if ts <= deadline:
                takeoff_end = ts
            else:
                break


            if flaps_at_takeoff and event.flaps is not None:
                if event.flaps == 0:
                    break

            if flaps_at_takeoff == 0 and event.gear == "up":
                break


        if takeoff_end is None:
            takeoff_end = deadline

        return takeoff_start, takeoff_end