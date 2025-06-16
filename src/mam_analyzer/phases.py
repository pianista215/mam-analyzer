from dateutil import parser
from datetime import datetime
from typing import List, Optional, Tuple

def parse_coordinate(value: str) -> float:
    return float(value.replace(",", "."))

def parse_timestamp(ts: str) -> datetime:
    """Parses ISO 8601 timestamps with flexible fractional seconds."""
    return parser.isoparse(ts)  

def detect_engine_start_phase(events: List[dict]) -> Optional[Tuple[datetime, datetime]]:
    """Detect from start until there is a location change (movement)."""
    start_time = None
    prev_lat = None
    prev_lon = None

    for event in events:
        ts = parse_timestamp(event["Timestamp"])
        changes = event.get("Changes", {})

        if start_time is None:
            start_time = ts

        lat_raw = changes.get("Latitude")
        lon_raw = changes.get("Longitude")

        if lat_raw and lon_raw:
            lat = parse_coordinate(lat_raw)
            lon = parse_coordinate(lon_raw)

            if prev_lat is not None and (lat != prev_lat or lon != prev_lon):
                return (start_time, ts)

            prev_lat = lat
            prev_lon = lon

    return None  # No movimiento detectado