from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.detectors.detector import Detector
from mam_analyzer.utils.engines import all_engines_are_off_from_status,get_engine_status
from mam_analyzer.utils.search import find_first_index_backward,find_first_index_backward_starting_from_idx
from mam_analyzer.utils.units import coords_differ

class ShutdownDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime],
        context: FlightDetectorContext,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect shutdown phase: Period with the plane in the position where the shutdown of the engines happens"""
        # In this detector we are not using from_time or to_time

        # Step 1 check if engines are stopped at the end
        # Look for the last full event to check status
        # Iterate over the rest index to see if the status is changed
        def fullEvent(e: FlightEvent) -> bool:
            return e.is_full_event()

        last_full_event_found = find_first_index_backward(
            events,
            fullEvent,
            from_time,
            to_time
        )

        if last_full_event_found is None:
            return None # No shutdown detected
        else:
            last_full_idx, last_full_event = last_full_event_found
        
        engine_status = get_engine_status(last_full_event)

        for idx in range(last_full_idx, len(events)):
            event = events[idx]
            for k,v in event.other_changes.items():
                if k.startswith("Engine "):
                    engine_num = int(k[7:])
                    engine_status[engine_num - 1] = v

        if not all_engines_are_off_from_status(engine_status):
            return None # The engines aren't off so no shutdown detected

        # Step 2: get the first event backward with different location
        shutdown_lat = last_full_event.latitude
        shutdown_lon = last_full_event.longitude

        def eventDiffLocation(e: FlightEvent) -> bool:
            return (
                e.latitude is not None and 
                e.longitude is not None and 
                (
                    coords_differ(e.latitude, shutdown_lat) or
                    coords_differ(e.longitude, shutdown_lon)
                )
            )

        last_diff_loc_event = find_first_index_backward_starting_from_idx(
            events,
            last_full_idx - 1,
            eventDiffLocation,
            from_time,
            to_time
        )

        if last_diff_loc_event is None:
            # Start is first event of the flight 
            # so a flight without takeoff and landing shouldn't be considered
            None
        else:
            start_diff_idx,_ = last_diff_loc_event
            start_shutdown = events[start_diff_idx + 1].timestamp
            end_shutdown = events[len(events) - 1].timestamp
            return start_shutdown,end_shutdown