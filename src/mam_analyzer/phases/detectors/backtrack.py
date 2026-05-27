from datetime import datetime
from math import sqrt, acos
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import unary_union
from typing import List, Optional, Tuple

from mam_analyzer.models.flight_context import FlightContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.utils.ground import is_on_air
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.runway import build_runway_polygon, match_runway_end
from mam_analyzer.utils.search import find_first_index_forward, find_first_index_backward
from mam_analyzer.utils.units import latlon_to_xy


class BacktrackDetector():

    BACKTRACK_THRESHOLD_METERS = 150             # min segment length (no runway polygon)
    BACKTRACK_THRESHOLD_WITH_RUNWAY_METERS = 60  # min segment length (with runway polygon)
    WIDTH_CORRIDOR = 30                          # half-width (m) of estimated corridor
    TURN_ZONE_RADIUS = 100                       # tolerance circle at runway ends
    BACKTRACK_DIRECTION_TOLERANCE_DEGREES = 30   # max angle from backtrack direction
    EXTEND_LINE_METERS = 2000

    def _vector_magnitude(self, v: Tuple[float, float]) -> float:
        """Return the magnitude (length) of a 2D vector."""
        return sqrt(v[0] ** 2 + v[1] ** 2)

    def extend_line(self, p1, p2, length):
        """Extend a line in both directions by 'length' meters."""
        (x1, y1), (x2, y2) = p1, p2
        dx = x2 - x1
        dy = y2 - y1
        L = self._vector_magnitude((dx, dy))
        if L == 0:
            return LineString([p1, p2])
        ux, uy = dx / L, dy / L
        p1_ext = (x1 - ux * length, y1 - uy * length)
        p2_ext = (x2 + ux * length, y2 + uy * length)
        return LineString([p1_ext, p2_ext])

    def angle_between_vectors(self, v1, v2):
        """Compute angle (in degrees) between two 2D vectors."""
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        mag1 = self._vector_magnitude(v1)
        mag2 = self._vector_magnitude(v2)
        if mag1 == 0 or mag2 == 0:
            return 0
        cos_theta = max(min(dot / (mag1 * mag2), 1), -1)
        return acos(cos_theta) * 180.0 / 3.14159265

    def _find_last_qualifying_segment(
        self,
        taxi_events_xy: List[Tuple],
        safe_zone,
        backtrack_direction: Tuple[float, float],
        threshold: float,
    ) -> Optional[Tuple[FlightEvent, FlightEvent]]:
        """Find the last consecutive run of taxi movements that are:
        - intersecting the safe zone (runway corridor or turn zone), and
        - moving within BACKTRACK_DIRECTION_TOLERANCE_DEGREES of backtrack_direction.

        Works with line segments between consecutive GPS points rather than
        individual points: GPS sampling can be sparse enough that points land
        just outside the runway polygon while the interpolated path is clearly
        on the runway.

        Only runs whose accumulated length >= threshold qualify.
        Returns (start_event, end_event) of the last qualifying run, or None.

        Taking the *last* qualifying segment avoids mistaking an earlier brief
        runway crossing for the actual backtrack.
        """
        runs = []           # list of (start_event, end_event, accumulated_length)
        current_run = []    # (xy, ev) pairs in the current run
        current_length = 0.0

        for i in range(len(taxi_events_xy) - 1):
            xy_curr, ev_curr = taxi_events_xy[i]
            xy_next, ev_next = taxi_events_xy[i + 1]

            mv = (xy_next[0] - xy_curr[0], xy_next[1] - xy_curr[1])
            in_zone = LineString([xy_curr, xy_next]).intersects(safe_zone)
            angle = self.angle_between_vectors(mv, backtrack_direction)

            if in_zone and angle <= self.BACKTRACK_DIRECTION_TOLERANCE_DEGREES:
                if not current_run:
                    current_run.append((xy_curr, ev_curr))
                current_run.append((xy_next, ev_next))
                current_length += self._vector_magnitude(mv)
            else:
                if current_run:
                    runs.append((current_run[0][1], current_run[-1][1], current_length))
                    current_run = []
                    current_length = 0.0

        if current_run:
            runs.append((current_run[0][1], current_run[-1][1], current_length))

        qualifying = [(start_ev, end_ev) for start_ev, end_ev, length in runs if length >= threshold]

        if not qualifying:
            return None

        return qualifying[-1]

    def detect_from_takeoff(
        self,
        taxi: FlightPhase,
        takeoff: FlightPhase,
        context: Optional[FlightContext] = None,
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

        # 2. Build corridor and safe zone
        runway_match = None
        if (
            context is not None
            and context.departure is not None
            and context.departure.runways
            and run_end_event.heading is not None
            and run_start_event.latitude is not None
            and run_start_event.longitude is not None
        ):
            runway_match = match_runway_end(
                context.departure,
                run_end_event.heading,
                run_start_event.latitude,
                run_start_event.longitude,
            )

        utm_zone = None
        if runway_match is not None:
            rwy, matched_end = runway_match
            opposite_end = rwy.ends[1] if matched_end is rwy.ends[0] else rwy.ends[0]
            takeoff_corridor, utm_zone = build_runway_polygon(rwy)
            matched_end_xy = latlon_to_xy(matched_end.latitude, matched_end.longitude, utm_zone)
            opposite_end_xy = latlon_to_xy(opposite_end.latitude, opposite_end.longitude, utm_zone)
            turn_zone_1 = Point(matched_end_xy).buffer(self.TURN_ZONE_RADIUS)
            turn_zone_2 = Point(opposite_end_xy).buffer(self.TURN_ZONE_RADIUS)
            safe_zone = unary_union([takeoff_corridor, turn_zone_1, turn_zone_2])
        else:
            takeoff_line = self.extend_line(run_start_xy, run_end_xy, length=self.EXTEND_LINE_METERS)
            takeoff_corridor = takeoff_line.buffer(self.WIDTH_CORRIDOR, cap_style=2)
            turn_zone = Point(run_start_xy).buffer(self.TURN_ZONE_RADIUS)
            safe_zone = unary_union([takeoff_corridor, turn_zone])

        # Takeoff direction and its opposite (= backtrack direction)
        takeoff_vector = (
            run_end_xy[0] - run_start_xy[0],
            run_end_xy[1] - run_start_xy[1],
        )
        backtrack_direction = (-takeoff_vector[0], -takeoff_vector[1])

        # 3. Build taxi segments line geometry
        taxi_coords = []
        taxi_events_xy = []
        for ev in taxi.events:
            if event_has_location(ev):
                xy = latlon_to_xy(ev.latitude, ev.longitude, utm_zone)
                taxi_coords.append(xy)
                taxi_events_xy.append((xy, ev))

        taxi_lines = MultiLineString(
            [LineString([taxi_coords[i], taxi_coords[i + 1]]) for i in range(len(taxi_coords) - 1)]
        )

        # 4. Quick filter: enough total overlap with corridor to be worth analysing
        threshold = self.BACKTRACK_THRESHOLD_WITH_RUNWAY_METERS if runway_match is not None else self.BACKTRACK_THRESHOLD_METERS
        if taxi_lines.intersection(takeoff_corridor).length < threshold:
            return None

        # 5. Find the last qualifying segment moving in the backtrack direction
        segment = self._find_last_qualifying_segment(
            taxi_events_xy, safe_zone, backtrack_direction, threshold
        )

        if segment is None:
            return None

        backtrack_start_event, _ = segment
        return backtrack_start_event.timestamp, taxi.end

    def detect_from_landing(
        self,
        taxi: FlightPhase,
        landing: FlightPhase,
        context: Optional[FlightContext] = None,
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

        # 2. Build corridor and safe zone
        runway_match = None
        if (
            context is not None
            and context.landing is not None
            and context.landing.runways
            and landing_start_event.heading is not None
            and landing_start_event.latitude is not None
            and landing_start_event.longitude is not None
        ):
            runway_match = match_runway_end(
                context.landing,
                landing_start_event.heading,
                landing_start_event.latitude,
                landing_start_event.longitude,
            )

        utm_zone = None
        if runway_match is not None:
            rwy, matched_end = runway_match
            opposite_end = rwy.ends[1] if matched_end is rwy.ends[0] else rwy.ends[0]
            landing_corridor, utm_zone = build_runway_polygon(rwy)
            matched_end_xy = latlon_to_xy(matched_end.latitude, matched_end.longitude, utm_zone)
            opposite_end_xy = latlon_to_xy(opposite_end.latitude, opposite_end.longitude, utm_zone)
            turn_zone_1 = Point(matched_end_xy).buffer(self.TURN_ZONE_RADIUS)
            turn_zone_2 = Point(opposite_end_xy).buffer(self.TURN_ZONE_RADIUS)
            safe_zone = unary_union([landing_corridor, turn_zone_1, turn_zone_2])
        else:
            landing_line = self.extend_line(landing_start_xy, landing_end_xy, length=self.EXTEND_LINE_METERS)
            landing_corridor = landing_line.buffer(self.WIDTH_CORRIDOR, cap_style=2)
            turn_zone = Point(landing_end_xy).buffer(self.TURN_ZONE_RADIUS)
            safe_zone = unary_union([landing_corridor, turn_zone])

        # Landing direction and its opposite (= backtrack direction)
        landing_vector = (
            landing_end_xy[0] - landing_start_xy[0],
            landing_end_xy[1] - landing_start_xy[1],
        )
        backtrack_direction = (-landing_vector[0], -landing_vector[1])

        # 3. Build taxi segments line geometry
        taxi_coords = []
        taxi_events_xy = []
        for ev in taxi.events:
            if event_has_location(ev):
                xy = latlon_to_xy(ev.latitude, ev.longitude, utm_zone)
                taxi_coords.append(xy)
                taxi_events_xy.append((xy, ev))

        taxi_lines = MultiLineString(
            [LineString([taxi_coords[i], taxi_coords[i + 1]]) for i in range(len(taxi_coords) - 1)]
        )

        # 4. Quick filter: enough total overlap with corridor to be worth analysing
        threshold = self.BACKTRACK_THRESHOLD_WITH_RUNWAY_METERS if runway_match is not None else self.BACKTRACK_THRESHOLD_METERS
        if taxi_lines.intersection(landing_corridor).length < threshold:
            return None

        # 5. Find the last qualifying segment moving in the backtrack direction
        segment = self._find_last_qualifying_segment(
            taxi_events_xy, safe_zone, backtrack_direction, threshold
        )

        if segment is None:
            return None

        _, backtrack_end_event = segment
        return taxi.start, backtrack_end_event.timestamp
