from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.detector import Detector
from mam_analyzer.context import FlightDetectorContext

class ShutdownDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        context: FlightDetectorContext,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect shutdown phase: until last event starting from the last position change."""
        start_time = None
        prev_lat = None
        prev_lon = None
        last_timestamp = None

        for event in reversed(events):
            ts = event.timestamp
            
            if last_timestamp is None:
                last_timestamp = ts

            if event.latitude is not None and event.longitude is not None:
                lat = event.latitude
                lon = event.longitude

                if prev_lat is not None and (lat != prev_lat or lon != prev_lon):
                    return (start_time, last_timestamp)

                prev_lat = lat
                prev_lon = lon

            start_time = ts

        return None