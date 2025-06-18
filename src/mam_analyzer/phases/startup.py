from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from mam_analyzer.detector import Detector
from mam_analyzer.utils.parsing import parse_coordinate, parse_timestamp
from mam_analyzer.context import FlightDetectorContext

class StartupDetector(Detector):
    def detect(
        self,
        events: List[Dict[str, Any]],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        context: FlightDetectorContext,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect startup phase: from first event until location changes (plane moves)."""
        start_time = None
        prev_lat = None
        prev_lon = None
        last_timestamp = None

        for event in events:
            ts = parse_timestamp(event["Timestamp"])
            if from_time and ts < from_time:
                continue
            if to_time and ts > to_time:
                break

            changes = event.get("Changes", {})

            if start_time is None:
                start_time = ts

            lat_raw = changes.get("Latitude")
            lon_raw = changes.get("Longitude")

            if lat_raw and lon_raw:
                lat = parse_coordinate(lat_raw)
                lon = parse_coordinate(lon_raw)

                if prev_lat is not None and (lat != prev_lat or lon != prev_lon):
                    return (start_time, last_timestamp)

                prev_lat = lat
                prev_lon = lon

            last_timestamp = ts

        return None