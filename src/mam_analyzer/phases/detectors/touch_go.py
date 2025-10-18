from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.detectors.detector import Detector
from mam_analyzer.utils.search import find_first_index_forward,find_first_index_forward_starting_from_idx
from mam_analyzer.utils.ground import is_on_air, is_on_ground
from mam_analyzer.utils.units import heading_within_range

class TouchAndGoDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime]
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect a touch&go: 
            From the moment the ground is touched (consider bounces) 
            until same conditions in takeoff (flaps up, gear up if flaps were up in the touch, or 1 minute)
            from_time and to_time must be provided in order to avoid colision with final_landing possible bounces
            from_time -> takeoff_end and to_time -> landing_start to avoid problems
        """

        if from_time is None or to_time is None:
            raise RuntimeError("TouchAndGoDetector must have from_time and to_time")


        # TODO: Pass events already filtered from from_time? or pass start index?
        def firstEvent(e: FlightEvent) -> bool:
            return e.timestamp >= from_time

        found_first_event = find_first_index_forward(
            events,
            firstEvent,
            from_time,
            to_time
        )

        if found_first_event is None:
            return None
        else:
            start_event_idx, _ = found_first_event

        # Step 1: look for the event when we touch the ground
        found_touch_event = find_first_index_forward_starting_from_idx(
            events,
            start_event_idx,
            is_on_ground,
            from_time,
            to_time
        )

        if found_touch_event is None:
            return None
        else:
            touch_idx, touch_event = found_touch_event

        touch_go_start = touch_event.timestamp


        # Step 2: check when we leave the ground again

        found_airborne = find_first_index_forward_starting_from_idx(
            events,
            touch_idx,
            is_on_air,
            from_time,
            to_time
        )

        if found_airborne is None:
            # Shouldn't happen, because should be detected as final_landing.
            return None
        else:
            airborne_idx, airborne_event = found_airborne

        # Step 3: check there are no bounces in the next 20 seconds
        look_for_bounces = True
        while look_for_bounces:
            limit_bounce = airborne_event.timestamp + timedelta(seconds=20)

            found_bounce = find_first_index_forward_starting_from_idx(
                events,
                airborne_idx,
                is_on_ground,
                from_time,
                limit_bounce
            )

            if found_bounce is not None:
                # There was a bounce look again for airborne
                bounce_idx, bounce_event = found_bounce
                found_airborne = find_first_index_forward_starting_from_idx(
                    events,
                    bounce_idx,
                    is_on_air,
                    from_time,
                    to_time
                )

                # TODO: encapsulate in function, duplicated code
                if found_airborne is None:
                    # Shouldn't happen, because should be detected as final_landing.
                    return None
                else:
                    airborne_idx, airborne_event = found_airborne
            else:
                look_for_bounces = False

        # Step 4: Look for the end of the takeoff phase from airbone_idx
        deadline = airborne_event.timestamp + timedelta(minutes=1)

        # TODO: From takeoff (create shared functions?)
        def lastTouchGoEvent(e: FlightEvent)->bool:
            return (
              touch_event.flaps != 0 and e.flaps == 0
              or
              touch_event.flaps == 0 and e.gear == "Up"
            )

        found_touch_go_end = find_first_index_forward_starting_from_idx(
            events,
            airborne_idx,
            lastTouchGoEvent,
            from_time,
            deadline
        )

        if found_touch_go_end is None:
            touch_go_end = deadline
        else:
            _, end_event = found_touch_go_end
            touch_go_end = end_event.timestamp

        return touch_go_start, touch_go_end


       