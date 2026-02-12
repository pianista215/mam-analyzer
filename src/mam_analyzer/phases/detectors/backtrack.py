from datetime import datetime
from math import sqrt, acos
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import unary_union
from typing import Optional, Tuple

from mam_analyzer.models.flight_context import FlightContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.utils.ground import is_on_air
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.runway import build_runway_polygon, match_runway_end, point_inside_runway
from mam_analyzer.utils.search import find_first_index_forward, find_first_index_backward
from mam_analyzer.utils.units import latlon_to_xy


class BacktrackDetector():

    BACKTRACK_THRESHOLD_METERS = 150      # min length required inside corridor to consider backtrack
    WIDTH_CORRIDOR = 30           # width (meters) of allowed takeoff/landing corridor
    TURN_ZONE_RADIUS = 100                # tolerance near runway threshold
    VECTOR_ANGLE_TOLERANCE_DEGREES = 3   # max angle deviation allowed
    EXTEND_LINE_METERS = 2000
    REVERSAL_NOISE_M = 10                 # ignore movements smaller than this on the runway axis

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

    def _has_reversal_on_runway(self, taxi_events, rwy):
        """Check if taxi events show a U-turn on the runway by detecting direction reversal
        along the runway axis. Returns (first_on_runway, last_on_runway) or None."""
        rwy_polygon = build_runway_polygon(rwy)

        # Runway axis in UTM for projection
        e1, e2 = rwy.ends
        e1_xy = latlon_to_xy(e1.latitude, e1.longitude)
        e2_xy = latlon_to_xy(e2.latitude, e2.longitude)
        dx = e2_xy[0] - e1_xy[0]
        dy = e2_xy[1] - e1_xy[1]
        axis_len = sqrt(dx**2 + dy**2)
        if axis_len == 0:
            return None
        ux, uy = dx / axis_len, dy / axis_len

        # Collect on-runway events with their projection onto the runway axis
        on_runway = []
        for ev in taxi_events:
            if event_has_location(ev):
                if point_inside_runway(ev.latitude, ev.longitude, rwy_polygon):
                    ev_xy = latlon_to_xy(ev.latitude, ev.longitude)
                    proj = (ev_xy[0] - e1_xy[0]) * ux + (ev_xy[1] - e1_xy[1]) * uy
                    on_runway.append((ev, proj))

        if len(on_runway) < 3:
            return None

        projections = [p for _, p in on_runway]

        # Find the initial significant direction of movement
        initial_direction = None
        for i in range(len(projections) - 1):
            delta = projections[i + 1] - projections[i]
            if abs(delta) > self.REVERSAL_NOISE_M:
                initial_direction = 1 if delta > 0 else -1
                break

        if initial_direction is None:
            return None

        # Look for significant movement in the opposite direction
        for i in range(len(projections) - 1):
            delta = projections[i + 1] - projections[i]
            if abs(delta) > self.REVERSAL_NOISE_M:
                direction = 1 if delta > 0 else -1
                if direction != initial_direction:
                    return on_runway[0][0], on_runway[-1][0]

        return None

    def detect_from_takeoff(
        self,
        taxi: FlightPhase,
        takeoff: FlightPhase,
        context: Optional[FlightContext] = None,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detects backtrack before takeoff using geometric analysis."""

        # 1. Identify takeoff reference events
        _, run_start_event = find_first_index_forward(
            takeoff.events, event_has_location, takeoff.start, takeoff.end
        )
        _, run_end_event = find_first_index_forward(
            takeoff.events, is_on_air, takeoff.start, takeoff.end
        )

        # 2. Context-based: any taxi event on the runway polygon is backtrack
        #    (if heading matched takeoff it would be in takeoff phase, not taxi)
        if (
            context is not None
            and context.departure is not None
            and context.departure.runways
            and run_end_event.heading is not None
        ):
            rwy_match = match_runway_end(
                context.departure,
                run_end_event.heading,
                run_end_event.latitude,
                run_end_event.longitude,
            )
            if rwy_match is not None:
                rwy, _ = rwy_match
                rwy_polygon = build_runway_polygon(rwy)
                for ev in taxi.events:
                    if event_has_location(ev) and point_inside_runway(ev.latitude, ev.longitude, rwy_polygon):
                        return ev.timestamp, taxi.end
                return None

        # 3. Fallback: estimated corridor from takeoff vector
        run_start_xy = latlon_to_xy(run_start_event.latitude, run_start_event.longitude)
        run_end_xy = latlon_to_xy(run_end_event.latitude, run_end_event.longitude)

        takeoff_line = self.extend_line(run_start_xy, run_end_xy, length=self.EXTEND_LINE_METERS)
        takeoff_corridor = takeoff_line.buffer(self.WIDTH_CORRIDOR, cap_style=2)
        turn_zone = Point(run_start_xy).buffer(self.TURN_ZONE_RADIUS)
        safe_zone = unary_union([takeoff_corridor, turn_zone])

        # Build taxi segments line geometry
        taxi_coords = []
        taxi_events_xy = []
        for ev in taxi.events:
            if event_has_location(ev):
                xy = latlon_to_xy(ev.latitude, ev.longitude)
                taxi_coords.append(xy)
                taxi_events_xy.append((xy, ev))

        if len(taxi_coords) < 2:
            return None

        taxi_lines = MultiLineString(
            [LineString([taxi_coords[i], taxi_coords[i + 1]]) for i in range(len(taxi_coords) - 1)]
        )

        # Check how much taxi is on top of the runway
        if taxi_lines.intersection(takeoff_corridor).length < self.BACKTRACK_THRESHOLD_METERS:
            return None  # no backtrack

        # Get the first event that is inside the backtrack
        for i in range(len(taxi_events_xy)):
            xy, ev = taxi_events_xy[i]
            point = Point(xy)
            if safe_zone.covers(point):
                return ev.timestamp, taxi.end

        return None

    def detect_from_landing(
        self,
        taxi: FlightPhase,
        landing: FlightPhase,
        context: Optional[FlightContext] = None,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detects backtrack after landing using geometric analysis."""

        # 1. Identify landing reference events
        _, landing_start_event = find_first_index_forward(
            landing.events, event_has_location, landing.start, landing.end
        )
        _, landing_end_event = find_first_index_backward(
            landing.events, event_has_location, landing.start, landing.end
        )

        # 2. Context-based: detect direction reversal on the runway
        if (
            context is not None
            and context.landing is not None
            and context.landing.runways
            and landing_start_event.heading is not None
        ):
            rwy_match = match_runway_end(
                context.landing,
                landing_start_event.heading,
                landing_start_event.latitude,
                landing_start_event.longitude,
            )
            if rwy_match is not None:
                rwy, _ = rwy_match
                result = self._has_reversal_on_runway(taxi.events, rwy)
                if result is not None:
                    _, last_on_runway = result
                    return taxi.start, last_on_runway.timestamp
                return None

        # 3. Fallback: estimated corridor from landing vector
        landing_start_xy = latlon_to_xy(landing_start_event.latitude, landing_start_event.longitude)
        landing_end_xy = latlon_to_xy(landing_end_event.latitude, landing_end_event.longitude)

        landing_line = self.extend_line(landing_start_xy, landing_end_xy, length=self.EXTEND_LINE_METERS)
        landing_corridor = landing_line.buffer(self.WIDTH_CORRIDOR, cap_style=2)
        turn_zone = Point(landing_end_xy).buffer(self.TURN_ZONE_RADIUS)
        safe_zone = unary_union([landing_corridor, turn_zone])

        # Build taxi segments line geometry
        taxi_coords = []
        taxi_events_xy = []
        for ev in taxi.events:
            if event_has_location(ev):
                xy = latlon_to_xy(ev.latitude, ev.longitude)
                taxi_coords.append(xy)
                taxi_events_xy.append((xy, ev))

        if len(taxi_coords) < 2:
            return None

        taxi_lines = MultiLineString(
            [LineString([taxi_coords[i], taxi_coords[i + 1]]) for i in range(len(taxi_coords) - 1)]
        )

        # Check how much taxi is on top of the runway
        if taxi_lines.intersection(landing_corridor).length < self.BACKTRACK_THRESHOLD_METERS:
            return None  # no backtrack

        # Get the last event that is inside the backtrack
        last_xy, backtrack_end_event = taxi_events_xy[0]

        for i in range(len(taxi_events_xy)):
            xy, ev = taxi_events_xy[i]
            point = Point(xy)

            if safe_zone.covers(point):
                # Still within safe region (runway corridor or turning circle)
                last_xy = xy
                backtrack_end_event = ev
            else:
                break

        if backtrack_end_event:
            return taxi.start, backtrack_end_event.timestamp

        return None
