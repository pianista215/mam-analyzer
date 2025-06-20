from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.detector import Detector
from mam_analyzer.utils.parsing import parse_coordinate, parse_timestamp
from mam_analyzer.context import FlightDetectorContext

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

        # Step 1: First event on air (onGround=False)
        for idx, event in enumerate(events):
            changes = event.get("Changes", {})
            if changes.get("onGround", "").lower() == "false":
                airborne_idx = idx
                airborne_heading = float(changes.get("Heading", "0"))
                flaps_raw = changes.get("Flaps")
                try:
                    flaps_at_takeoff = int(flaps_raw) if flaps_raw is not None else 0
                except ValueError:
                    flaps_at_takeoff = 0
                break

        if airborne_idx is None:
            return None  # Takeoff not detected

        # Step 2: Look back until the last event with heading on range
        for i in range(airborne_idx - 1, -1, -1):
            changes = events[i].get("Changes", {})
            heading_raw = changes.get("Heading")
            on_ground = changes.get("onGround", "").lower()
            if heading_raw is None:
                continue
            try:
                heading = float(heading_raw)
            except ValueError:
                continue

            if on_ground != "true":
                break  # Not in ground

            if not heading_within_range(heading, airborne_heading):
                break  # Heading drastically changes

            takeoff_start = parser.parse(events[i]["Timestamp"])

        if takeoff_start is None:
            # If we don't find nothing use airbone event as first
            takeoff_start = parser.parse(events[airborne_idx]["Timestamp"])

        # Paso 3: Look for the end of the takeoff phase from airbone_idx
        deadline = parser.parse(events[airborne_idx]["Timestamp"]) + timedelta(minutes=1)

        for event in events[airborne_idx + 1:]:
            ts = parser.parse(event["Timestamp"])
            changes = event.get("Changes", {})

            if flaps_at_takeoff and "Flaps" in changes:
                try:
                    if int(changes["Flaps"]) == 0:
                        takeoff_end = ts
                        break
                except ValueError:
                    pass

            if flaps_at_takeoff == 0 and changes.get("Gear", "").lower() == "up":
                takeoff_end = ts
                break

            if ts > deadline:
                takeoff_end = ts
                break

        if takeoff_end is None:
            takeoff_end = deadline

        return takeoff_start, takeoff_end

    def _find_first_airbone_event(
        events: List[Dict[str, Any]],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        ) -> Optional[Dic[str, Any]]:
        """Detect the takeoff event (onGround=false). It should have all the important info itself"""
        for event in events:
            ts = parse_timestamp(event["Timestamp"])
            if from_time and ts < from_time:
                continue
            if to_time and ts > to_time:
                break   

                ## CONTINUA UNAI