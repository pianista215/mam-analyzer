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