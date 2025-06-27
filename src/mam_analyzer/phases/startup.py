from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.detector import Detector
from mam_analyzer.context import FlightDetectorContext

class StartupDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        context: FlightDetectorContext,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect startup phase: from first event (if engines are off) until location changes (plane moves)."""
        start_time = None
        prev_lat = None
        prev_lon = None
        last_timestamp = None

        for event in events:
            ts = event.timestamp
            if from_time and ts < from_time: #TODO: Not used check if needed
                continue
            if to_time and ts > to_time:
                break

            if start_time is None:
                if event.has_started_engines is not None and event.has_started_engines:
                    return None
                else:
                    start_time = ts

            if event.latitude is not None and event.longitude is not None:
                lat = event.latitude
                lon = event.longitude

                if prev_lat is not None and (lat != prev_lat or lon != prev_lon):
                    return (start_time, last_timestamp)

                prev_lat = lat
                prev_lon = lon

            last_timestamp = ts

        return None