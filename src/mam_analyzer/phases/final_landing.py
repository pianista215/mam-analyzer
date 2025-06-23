from datetime import datetime,timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.detector import Detector
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
        for idx in range(len(events) - 1, -1, -1):
            event = events[idx]
            if event.other_changes.get("LandingVSFpm") is not None:
                touch_idx = idx
                touch_heading = event.heading
                landing_start = event.timestamp
                break


        if landing_start is None:
            return None  # Landing not detected

        # Step 2: Look for the end of the landing until heading variate from touch_idx
        # TODO: Needed limit of time or check speed?
        for idx in range(touch_idx + 1, len(events)):
            event = events[idx]
            if event.heading is not None and not heading_within_range(touch_heading, event.heading):
                landing_end = events[idx - 1].timestamp
                break

        if landing_end is None:
            # Just the last event
            landing_end = events[-1].timestamp                    


        return landing_start, landing_end