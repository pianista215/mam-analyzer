from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

from mam_analyzer.utils.parsing import parse_coordinate, parse_timestamp


@dataclass(slots=True)
class FlightEvent:
    timestamp: datetime
    on_ground: Optional[bool] = None
    heading: Optional[int] = None
    flaps: Optional[int] = None
    gear: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    started_engines: Optional[bool] = None

    # Other changes not so important to trace
    other_changes: Dict[str, str] = None

    @staticmethod
    def from_json(event: Dict[str, Any]) -> "FlightEvent":
        changes = event.get("Changes", {})
        ts = parse_timestamp(event["Timestamp"])

        def parse_bool(val: Optional[str]) -> Optional[bool]:
            if val is None:
                return None
            return val.strip().lower() == "true"

        def parse_int(val: Optional[str]) -> Optional[int]:
            if val is None:
                return None
            try:
                return int(val)
            except ValueError:
                return None

        _started_engines = any(
            key.startswith("Engine ") and key[7:].isdigit() and 1 <= int(key[7:]) <= 4 and value == "On"
            for key, value in changes.items()
        )                

        return FlightEvent(
            timestamp=ts,
            latitude=parse_coordinate(changes.get("Latitude")) if "Latitude" in changes else None,
            longitude=parse_coordinate(changes.get("Longitude")) if "Longitude" in changes else None,
            on_ground=parse_bool(changes.get("onGround")),
            heading=parse_int(changes.get("Heading")),
            flaps=parse_int(changes.get("Flaps")),
            gear=changes.get("Gear"),
            started_engines = _started_engines,
            other_changes=changes
        )