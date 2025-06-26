from datetime import datetime,timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.detector import Detector
from mam_analyzer.utils.search import find_first_index_forward,find_first_index_forward_starting_from_idx
from mam_analyzer.utils.units import heading_within_range

class FinalLandingDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        context: FlightDetectorContext,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect the last landing: from the moment the ground is touched until we leave the runway."""
        touch_idx = None
        touch_heading = None
        landing_start = None
        landing_end = None

        # Step 1: First event with LandingVSFpm
        def withLandingVSFpm(e: FlightEvent) -> bool:
            return e.other_changes.get("LandingVSFpm") is not None

        found_landing = find_first_index_forward(
            events,
            withLandingVSFpm,
            from_time,
            to_time
        )

        if found_landing is None:
            return None  # Landing not detected
        else:
            touch_idx, landing_event = found_landing
            touch_heading = landing_event.heading
            landing_start = landing_event.timestamp

        # Step 2: Look for the end of the landing until heading variate from touch_idx
        # TODO: Needed limit of time or check speed?

        def headingOutOfRange(e: FlightEvent) -> bool:
            return (
                e.heading is not None 
                and not heading_within_range(touch_heading, e.heading)
            )

        found_end_landing = find_first_index_forward_starting_from_idx(
            events,
            touch_idx + 1,
            headingOutOfRange,
            from_time,
            to_time
        )

        if found_end_landing is None:
            # Just the last event
            landing_end = events[-1].timestamp
        else:
            first_bad_heading_idx, _ = found_end_landing
            landing_end = events[first_bad_heading_idx - 1].timestamp                

        return landing_start, landing_end