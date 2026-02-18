from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.detectors.detector import Detector
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.runway import build_runway_polygon, match_runway_end, point_inside_runway
from mam_analyzer.utils.search import find_first_index_backward,find_first_index_forward_starting_from_idx,find_first_index_backward_starting_from_idx
from mam_analyzer.utils.units import haversine, heading_within_range

class FinalLandingDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        context: Optional["FlightContext"] = None,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect the last landing: from the moment the ground is touched until we leave the runway."""
        touch_idx = None
        touch_heading = None
        landing_start = None
        landing_end = None

        # Step 1: Ensure the aircraft is on ground at the end of the flight
        def lastFullEvent(e: FlightEvent) -> bool:
            return e.is_full_event()

        found_last_full_event = find_first_index_backward(
            events,
            lastFullEvent,
            from_time,
            to_time
        )

        if found_last_full_event is None:
            # Weird there should be enough full events
            return None
        else:
            _, last_full_event = found_last_full_event
            if last_full_event.on_ground != True:
                return None


        # Step 2: First event with LandingVSFpm from backward
        def withLandingVSFpm(e: FlightEvent) -> bool:
            return e.other_changes.get("LandingVSFpm") is not None

        found_landing = find_first_index_backward(
            events,
            withLandingVSFpm,
            from_time,
            to_time
        )

        if found_landing is None:
            return None  # Landing not detected
        else:
            touch_idx, landing_event = found_landing
            touch_heading = landing_event.heading
            landing_start = landing_event.timestamp

        # Step 3: Detect possible double bounces look in previous 10 seconds was another touch
        delta = landing_start + timedelta(seconds=-10)

        found_bounce = find_first_index_backward_starting_from_idx(
            events,
            touch_idx - 1,
            withLandingVSFpm,
            delta,
            to_time
        )

        if found_bounce is not None:
            print("Found bounce! Updating touch")
            touch_idx, landing_event = found_bounce
            touch_heading = landing_event.heading
            landing_start = landing_event.timestamp


        # Step 4: Look for the end of the landing (exit the runway)
        runway_match = None
        if (
            context is not None
            and context.landing is not None
            and context.landing.runways
            and landing_event.latitude is not None
            and landing_event.longitude is not None
        ):
            runway_match = match_runway_end(
                context.landing,
                touch_heading,
                landing_event.latitude,
                landing_event.longitude,
            )

        if runway_match is not None:
            rwy, matched_end = runway_match
            # Opposite threshold: if we land on 01, aim for the 19 end
            opposite_end = rwy.ends[1] if matched_end is rwy.ends[0] else rwy.ends[0]
            rwy_polygon, utm_zone = build_runway_polygon(rwy)

            min_distance = haversine(
                landing_event.latitude, landing_event.longitude,
                opposite_end.latitude, opposite_end.longitude,
            )
            landing_end = events[-1].timestamp

            for idx in range(touch_idx + 1, len(events)):
                e = events[idx]
                if event_has_location(e):
                    # Left the runway polygon → landing over
                    if not point_inside_runway(e.latitude, e.longitude, rwy_polygon, utm_zone):
                        landing_end = events[idx - 1].timestamp
                        break

                    # Distance to opposite threshold increasing → landing over
                    curr_distance = haversine(
                        e.latitude, e.longitude,
                        opposite_end.latitude, opposite_end.longitude,
                    )
                    if curr_distance > min_distance:
                        landing_end = events[idx - 1].timestamp
                        break
                    else:
                        min_distance = curr_distance
        else:
            def headingOutOfRange(e: FlightEvent) -> bool:
                return (
                    e.heading is not None
                    and not heading_within_range(touch_heading, e.heading)
                )

            found_end_landing = find_first_index_forward_starting_from_idx(
                events,
                touch_idx + 1,
                headingOutOfRange,
                from_time,
                to_time
            )

            if found_end_landing is None:
                # Just the last event
                landing_end = events[-1].timestamp
            else:
                first_bad_heading_idx, _ = found_end_landing
                landing_end = events[first_bad_heading_idx - 1].timestamp

        return landing_start, landing_end