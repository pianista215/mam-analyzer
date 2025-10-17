from datetime import datetime, timedelta
from math import atan2, degrees, sqrt
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import unary_union
from typing import List, Optional, Tuple

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.utils.ground import is_on_air
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.search import find_first_index_forward
from mam_analyzer.utils.units import latlon_to_xy


class BacktrackDetector():

    BACKTRACK_THRESHOLD_METERS = 150  # min to consider backtrack
    TAKEOFF_WIDTH_CORRIDOR = 30 #meters each side of takeoff line
    ANGLE_TOLERANCE = 8 

    def extend_line(self, p1, p2, length):
        """Extiende un segmento p1->p2 en ambos extremos."""
        (x1, y1), (x2, y2) = p1, p2
        dx = x2 - x1
        dy = y2 - y1
        L = sqrt(dx*dx + dy*dy)
        if L == 0:
            return LineString([p1, p2])  # evitar dividir entre cero
        ux, uy = dx / L, dy / L  # vector unitario
        # Crear nuevos puntos extendidos
        p1_ext = (x1 - ux * length, y1 - uy * length)
        p2_ext = (x2 + ux * length, y2 + uy * length)
        return LineString([p1_ext, p2_ext])

    def detect_from_takeoff(
        self,
        taxi: FlightPhase,
        takeoff: FlightPhase,
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect if there is backtrack previous to takeoff."""

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

        # Extiende la linea 200m en cada sentido
        takeoff_line = self.extend_line(run_start_xy, run_end_xy, length=200)

        #takeoff_line = LineString([run_start_xy, run_end_xy])
        takeoff_corridor = takeoff_line.buffer(self.TAKEOFF_WIDTH_CORRIDOR, cap_style=2)
        turn_zone = Point(run_start_xy).buffer(100) # 100m de tolerancia para el giro

        safe_zone = unary_union([takeoff_corridor, turn_zone])

        # Vector of takeoff (for angle comparison)
        dx = run_end_xy[0] - run_start_xy[0]
        dy = run_end_xy[1] - run_start_xy[1]
        takeoff_angle = degrees(atan2(dy, dx))
        takeoff_bearing = (450 - takeoff_angle) % 360
        print(f"Takeoff bearing {takeoff_bearing}")

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
        last_xy, backtrack_start_event = taxi_events_xy[-1]  # ✅ bug arreglado

        for i in reversed(range(len(taxi_events_xy) - 1)):
            xy, ev = taxi_events_xy[i]
            point = Point(xy)

            # ✅ Si está dentro de la zona segura, actualizamos y seguimos
            if safe_zone.covers(point):
                last_xy = xy
                backtrack_start_event = ev
            else:
                # Si sale de zona segura, comprobar si es alineación con la pista
                seg_dx = last_xy[0] - xy[0]
                seg_dy = last_xy[1] - xy[1]
                seg_angle = degrees(atan2(seg_dy, seg_dx))
                seg_bearing = (450 - seg_angle) % 360

                angle_diff = abs(seg_bearing - takeoff_bearing)
                angle_diff = min(angle_diff, 360 - angle_diff)  # ✅ normalizar

                if angle_diff <= self.ANGLE_TOLERANCE:
                    # Aún está alineado, lo aceptamos
                    last_xy = xy
                    backtrack_start_event = ev
                else:
                    # Rompe la búsqueda
                    break


        if backtrack_start_event:
            return backtrack_start_event.timestamp, taxi.end

        return None
