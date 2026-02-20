from datetime import datetime,timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.detectors.detector import Detector
from mam_analyzer.utils.ground import is_on_air
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.runway import build_runway_polygon, match_runway_for_takeoff, point_inside_runway
from mam_analyzer.utils.search import find_first_index_forward,find_first_index_backward_starting_from_idx,find_first_index_forward_starting_from_idx
from mam_analyzer.utils.units import haversine, heading_within_range

class TakeoffDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        context: Optional["FlightContext"] = None,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect the first takeoff: from the start of takeoff run until flaps 0, gear up or 1 minute."""
        airborne_idx = None
        airborne_heading = None
        takeoff_start = None
        takeoff_end = None
        flaps_at_takeoff = None

        # Step 1: First event on air (onGround=False)
        found_airborne = find_first_index_forward(
            events,
            is_on_air,
            from_time,
            to_time
        )

        if found_airborne is None:
            return None  # Takeoff not detected
        else:
            airborne_idx, airborne_event = found_airborne
            airborne_heading = airborne_event.heading
            flaps_at_takeoff = airborne_event.flaps

        # Step 2: Look backward for the start of the takeoff run
        runway_match = None
        if (
            context is not None
            and context.departure is not None
            and context.departure.runways
            and airborne_event.latitude is not None
            and airborne_event.longitude is not None
        ):
            runway_match = match_runway_for_takeoff(
                context.departure,
                events,
                airborne_idx,
                airborne_event,
                airborne_heading,
            )

        if runway_match is not None:
            rwy, matched_end = runway_match
            rwy_polygon, utm_zone = build_runway_polygon(rwy)

            min_distance = haversine(
                airborne_event.latitude, airborne_event.longitude,
                matched_end.latitude, matched_end.longitude,
            )
            takeoff_start = events[0].timestamp

            for idx in range(airborne_idx - 1, -1, -1):
                e = events[idx]
                if event_has_location(e):
                    inside = point_inside_runway(e.latitude, e.longitude, rwy_polygon, utm_zone)
                    if not inside:
                        takeoff_start = events[idx + 1].timestamp
                        break

                    curr_distance = haversine(
                        e.latitude, e.longitude,
                        matched_end.latitude, matched_end.longitude,
                    )
                    if curr_distance > min_distance:
                        takeoff_start = events[idx + 1].timestamp
                        break
                    else:
                        min_distance = curr_distance
        else:
            def headingIsOutOfRange(e: FlightEvent)->bool:
                return (
                    e.heading is not None
                    and not heading_within_range(e.heading, airborne_heading)
                )

            found_diff_heading = find_first_index_backward_starting_from_idx(
                events,
                airborne_idx - 1,
                headingIsOutOfRange,
                from_time,
                to_time
            )

            if found_diff_heading is None:
                # If all previous events are in correct heading use first event
                takeoff_start = events[0].timestamp
            else:
                diff_heading_idx, _ = found_diff_heading
                takeoff_start = events[diff_heading_idx + 1].timestamp

        # Step 3: Look for the end of the takeoff phase from airbone_idx
        deadline = events[airborne_idx].timestamp + timedelta(minutes=1)

        def lastTakeoffEvent(e: FlightEvent)->bool:
            return (
              flaps_at_takeoff != 0 and e.flaps == 0
              or
              flaps_at_takeoff == 0 and e.gear == "Up"
            )

        found_takeoff_end = find_first_index_forward_starting_from_idx(
            events,
            airborne_idx,
            lastTakeoffEvent,
            from_time,
            deadline
        )

        if found_takeoff_end is None:
            takeoff_end = deadline
        else:
            _, end_event = found_takeoff_end
            takeoff_end = end_event.timestamp

        return takeoff_start, takeoff_end
