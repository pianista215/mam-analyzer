from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.detectors.detector import Detector
from mam_analyzer.utils.engines import all_engines_are_off, all_engines_are_on
from mam_analyzer.utils.search import find_first_index_forward,find_first_index_forward_starting_from_idx
from mam_analyzer.utils.units import coords_differ

class StartupDetector(Detector):
    def detect(
        self,
        events: List[FlightEvent],
        from_time: Optional[datetime],
        to_time: Optional[datetime]
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect startup phase: from first event (if engines are off) until location changes after engines are on."""
        # In this detector we are not using from_time or to_time

        first_event = events[0]

        # Step 1: Check we start from engines off
        if not all_engines_are_off(first_event):
            return None # No startup detected. Some engine was started

        start_time = first_event.timestamp

        # Step 2: look for the first full event with all engines started
        def firstFullEventBothStarted(e: FlightEvent) -> bool:
            return e.is_full_event() and all_engines_are_on(e)

        found_engines_started = find_first_index_forward(
            events,
            firstFullEventBothStarted,
            from_time,
            to_time
        )

        if found_engines_started is None:
            return None
        else:
            engines_started_idx, engines_started_event = found_engines_started
            started_lat = engines_started_event.latitude
            started_lon = engines_started_event.longitude

        # Step 3: look for the first event with different location
        def eventDiffLocation(e: FlightEvent) -> bool:
            return (
                e.latitude is not None and 
                e.longitude is not None and 
                (
                    coords_differ(e.latitude, started_lat) or
                    coords_differ(e.longitude, started_lon)
                )
            )

        found_startup_end = find_first_index_forward_starting_from_idx(
            events,
            engines_started_idx,
            eventDiffLocation,
            from_time,
            to_time
        )

        if found_startup_end is None: 
            return start_time, events[len(events) - 1].timestamp #All events are startup
        else:
            end_idx, x = found_startup_end
            return start_time, events[end_idx - 1].timestamp