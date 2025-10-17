from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.utils.ground import is_on_air
from mam_analyzer.utils.search import find_first_index_forward

class BacktrackDetector():
    def detect_from_takeoff(
        self,
        taxi: FlightPhase,
        takeoff: FlightPhase,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect if there are backtrack in the taxi and return how it start"""
        # Step 1: Get takeoff run vector

        takeoff_events = takeoff.events
        run_start_event = takeoff_events[0]

        _, run_end_event = find_first_index_forward(
            takeoff_events, 
            is_on_air, 
            takeoff.start, 
            takeoff.end
        )


        