from datetime import datetime,timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.detector import Detector
from mam_analyzer.utils.parsing import parse_coordinate, parse_timestamp
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
        for idx, event in enumerate(events):
            if event.on_ground is not None and event.on_ground is False:
                airborne_idx = idx
                airborne_heading = event.heading
                flaps_at_takeoff = event.flaps
                break

        if airborne_idx is None:
            return None  # Takeoff not detected

        # Step 2: Look back until the last event with heading on range
        for i in range(airborne_idx - 1, -1, -1):
            back_event = events[i]
            heading = back_event.heading
            on_ground = back_event.on_ground

            if heading is None:
                continue

            if on_ground is False:
                break  # Not in ground

            if not heading_within_range(heading, airborne_heading):
                break  # Heading drastically changes

            takeoff_start = back_event.timestamp

        if takeoff_start is None:
            # If we don't find nothing use airbone event as first
            takeoff_start = events[airborne_idx].timestamp
            
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