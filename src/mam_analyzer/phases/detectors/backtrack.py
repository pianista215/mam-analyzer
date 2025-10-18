from datetime import datetime
from math import sqrt, acos
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import unary_union
from typing import Optional, Tuple

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.utils.ground import is_on_air
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.search import find_first_index_forward, find_first_index_backward
from mam_analyzer.utils.units import latlon_to_xy


class BacktrackDetector():

    BACKTRACK_THRESHOLD_METERS = 150      # min length required inside corridor to consider backtrack
    WIDTH_CORRIDOR = 30           # width (meters) of allowed takeoff/landing corridor
    TURN_ZONE_RADIUS = 100                # tolerance near runway threshold
    VECTOR_ANGLE_TOLERANCE_DEGREES = 3   # max angle deviation allowed
    EXTEND_LINE_METERS = 300

    def extend_line(self, p1, p2, length):
        """Extend a line in both directions by 'length' meters."""
        (x1, y1), (x2, y2) = p1, p2
        dx = x2 - x1
        dy = y2 - y1
        L = sqrt(dx*dx + dy*dy)
        if L == 0:
            return LineString([p1, p2])  # avoid zero division
        ux, uy = dx / L, dy / L  # unit vector
        p1_ext = (x1 - ux * length, y1 - uy * length)
        p2_ext = (x2 + ux * length, y2 + uy * length)
        return LineString([p1_ext, p2_ext])

    def angle_between_vectors(self, v1, v2):
        """Compute angle (in degrees) between two 2D vectors."""
        dot = v1[0]*v2[0] + v1[1]*v2[1]
        mag1 = sqrt(v1[0]**2 + v1[1]**2)
        mag2 = sqrt(v2[0]**2 + v2[1]**2)
        if mag1 == 0 or mag2 == 0:
            return 0
        cos_theta = max(min(dot / (mag1 * mag2), 1), -1)  # numerical safety
        return acos(cos_theta) * 180.0 / 3.14159265

    def detect_from_takeoff(
        self,
        taxi: FlightPhase,
        takeoff: FlightPhase,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detects backtrack before takeoff using geometric analysis."""

        # 1. Identify runway motion vector
        _, run_start_event = find_first_index_forward(
            takeoff.events, event_has_location, takeoff.start, takeoff.end
        )
        _, run_end_event = find_first_index_forward(
            takeoff.events, is_on_air, takeoff.start, takeoff.end
        )

        run_start_xy = latlon_to_xy(run_start_event.latitude, run_start_event.longitude)
        run_end_xy = latlon_to_xy(run_end_event.latitude, run_end_event.longitude)

        # 2. Extend runway line for geometric corridor detection
        takeoff_line = self.extend_line(run_start_xy, run_end_xy, length=self.EXTEND_LINE_METERS)
        takeoff_corridor = takeoff_line.buffer(self.WIDTH_CORRIDOR, cap_style=2)
        turn_zone = Point(run_start_xy).buffer(self.TURN_ZONE_RADIUS)
        safe_zone = unary_union([takeoff_corridor, turn_zone])

        # Reference vector (true takeoff direction)
        takeoff_vector = (
            run_end_xy[0] - run_start_xy[0],
            run_end_xy[1] - run_start_xy[1]
        )

        # 3. Build taxi segments line geometry
        taxi_coords = []
        taxi_events_xy = []
        for ev in taxi.events:
            if event_has_location(ev):
                xy = latlon_to_xy(ev.latitude, ev.longitude)
                taxi_coords.append(xy)
                taxi_events_xy.append((xy, ev))

        taxi_lines = MultiLineString(
            [LineString([taxi_coords[i], taxi_coords[i + 1]]) for i in range(len(taxi_coords) - 1)]
        )

        # 4. Check how much taxi is on top of the runway
        if taxi_lines.intersection(takeoff_corridor).length < self.BACKTRACK_THRESHOLD_METERS:
            return None  # no backtrack

        # 5. Walk backwards to find where backtrack starts
        last_xy, backtrack_start_event = taxi_events_xy[-1]

        for i in reversed(range(len(taxi_events_xy) - 1)):
            xy, ev = taxi_events_xy[i]
            point = Point(xy)

            if safe_zone.covers(point):
                # Still within safe region (runway corridor or turning circle)
                last_xy = xy
                backtrack_start_event = ev
            else:
                # Outside safe area → verify alignment using vector angle
                movement_vector = (xy[0] - run_start_xy[0], xy[1] - run_start_xy[1])
                angle = self.angle_between_vectors(takeoff_vector, movement_vector)

                if angle <= self.VECTOR_ANGLE_TOLERANCE_DEGREES:
                    # Still moving along runway direction
                    last_xy = xy
                    backtrack_start_event = ev
                else:
                    break  # significant deviation → backtrack begins here

        if backtrack_start_event:
            return backtrack_start_event.timestamp, taxi.end

        return None

    def detect_from_landing(
        self,
        taxi: FlightPhase,
        landing: FlightPhase,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detects backtrack after landing using geometric analysis."""

        # 1. Identify runway motion vector
        _, landing_start_event = find_first_index_forward(
            landing.events, event_has_location, landing.start, landing.end
        )
        _, landing_end_event = find_first_index_backward(
            landing.events, event_has_location, landing.start, landing.end
        )

        landing_start_xy = latlon_to_xy(landing_start_event.latitude, landing_start_event.longitude)
        landing_end_xy = latlon_to_xy(landing_end_event.latitude, landing_end_event.longitude)

        # 2. Extend runway line for geometric corridor detection
        landing_line = self.extend_line(landing_start_xy, landing_end_xy, length=self.EXTEND_LINE_METERS)
        landing_corridor = landing_line.buffer(self.WIDTH_CORRIDOR, cap_style=2)
        turn_zone = Point(landing_end_xy).buffer(self.TURN_ZONE_RADIUS)
        safe_zone = unary_union([landing_corridor, turn_zone])

        # Reference vector (true landing direction)
        landing_vector = (
            landing_end_xy[0] - landing_start_xy[0],
            landing_end_xy[1] - landing_start_xy[1]
        )

        # 3. Build taxi segments line geometry
        taxi_coords = []
        taxi_events_xy = []
        for ev in taxi.events:
            if event_has_location(ev):
                xy = latlon_to_xy(ev.latitude, ev.longitude)
                taxi_coords.append(xy)
                taxi_events_xy.append((xy, ev))

        taxi_lines = MultiLineString(
            [LineString([taxi_coords[i], taxi_coords[i + 1]]) for i in range(len(taxi_coords) - 1)]
        )

        # 4. Check how much taxi is on top of the runway
        if taxi_lines.intersection(landing_corridor).length < self.BACKTRACK_THRESHOLD_METERS:
            return None  # no backtrack

        # 5. Walk to find where backtrack ends
        last_xy, backtrack_end_event = taxi_events_xy[0]

        for i in range(1, len(taxi_events_xy)):
            xy, ev = taxi_events_xy[i]
            point = Point(xy)

            if safe_zone.covers(point):
                # Still within safe region (runway corridor or turning circle)
                last_xy = xy
                backtrack_end_event = ev
            else:
                # Outside safe area → verify alignment using vector angle
                movement_vector = (xy[0] - landing_end_xy[0], xy[1] - landing_end_xy[1])
                angle = self.angle_between_vectors(landing_vector, movement_vector)

                if angle <= self.VECTOR_ANGLE_TOLERANCE_DEGREES:
                    # Still moving along runway direction
                    last_xy = xy
                    backtrack_end_event = ev
                else:
                    break  # significant deviation → backtrack begins here

        if backtrack_end_event:
            return taxi.start, backtrack_end_event.timestamp

        return None        
