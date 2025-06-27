from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.detector import Detector
from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.utils.search import find_first_index_backward

class ShutdownDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        context: FlightDetectorContext,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect shutdown phase: Period with the plane in the position where the shutdown of the engines happens"""

        # Step 1 check if engines are stopped in the last 3 minutes events
        last_event_timestamp = events[len(events) - 1].timestamp 
        delta = last_event_timestamp + timedelta(minutes=-3)

        def enginesOff(e: FlightEvent) -> bool:
            return e.has_started_engines == False

        found_stopped = find_first_index_backward(
            events,
            enginesOff,
            delta,
            to_time
        )

        if found_stopped is None:
            return None # No shutdown detected
        else:
            stopped_idx, stopped_event = found_stopped




        start_time = None
        last_lat = None
        last_lon = None
        last_timestamp = None

        for event in reversed(events):
            ts = event.timestamp
            
            if last_timestamp is None:
                last_timestamp = ts

            if last_lat is None and last_lon is None:
                if event.latitude is not None and event.longitude is not None:
                    last_lat = event.latitude
                    last_lon = event.longitude
                    start_time = ts
            else:
                if event.latitude is not None and event.longitude is not None:
                    if last_lat != event.latitude or last_lon != event.longitude:
                        return (start_time, last_timestamp)
                    else:
                        start_time = ts

        return None