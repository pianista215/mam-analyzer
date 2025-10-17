from datetime import datetime, timedelta
from shapely.geometry import LineString, MultiLineString
from typing import List, Optional, Tuple

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.utils.ground import is_on_air
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.search import find_first_index_forward
from mam_analyzer.utils.units import latlon_to_xy


class BacktrackDetector():

    BACKTRACK_THRESHOLD_METERS = 150  # mínimo para considerar backtrack

    def detect_from_takeoff(
        self,
        taxi: FlightPhase,
        takeoff: FlightPhase,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detecta si hubo backtrack durante el taxi antes del despegue."""

        # Step 1: Create the takeoff corridor
        takeoff_events = takeoff.events

        _, run_start_event = find_first_index_forward(
            takeoff_events, 
            event_has_location, 
            takeoff.start, 
            takeoff.end
        )
        _, run_end_event = find_first_index_forward(
            takeoff_events, 
            is_on_air, 
            takeoff.start, 
            takeoff.end
        )

        run_start_xy = latlon_to_xy(run_start_event.latitude, run_start_event.longitude)
        run_end_xy = latlon_to_xy(run_end_event.latitude, run_end_event.longitude)

        takeoff_line = LineString([run_start_xy, run_end_xy])
        takeoff_corridor = takeoff_line.buffer(20, cap_style=2)  # 20m a cada lado

        # Step 2: taxi multiline
        taxi_coords = []
        taxi_events_xy = []  # Save to later get the backtrack start if it's detected
        for ev in taxi.events:
            if event_has_location(ev):
                xy = latlon_to_xy(ev.latitude, ev.longitude)
                taxi_coords.append(xy)
                taxi_events_xy.append((xy, ev))

        taxi_segments = []
        for i in range(len(taxi_coords) - 1):
            seg = LineString([taxi_coords[i], taxi_coords[i + 1]])
            taxi_segments.append(seg)

        taxi_lines = MultiLineString(taxi_segments)

        # Step 3: See where the corridor intersects with taxi
        intersection = taxi_lines.intersection(takeoff_corridor)
        distance_inside = intersection.length  # meters

        if distance_inside < self.BACKTRACK_THRESHOLD_METERS:
            return None 

        # Step 4: Start of backtrack
        # Iterate backwards to see first point out of corridor
        backtrack_start_event = None
        inside_backtrack = False

        for (xy, ev) in reversed(taxi_events_xy):
            point = LineString([xy])

            if takeoff_corridor.covers(point):
                inside_backtrack = True
                backtrack_start_event = ev
            elif inside_backtrack:
                # We are out of the takeoff_corridor
                break

        # Result
        if backtrack_start_event:
            return (backtrack_start_event.timestamp, taxi.end)

        return None
