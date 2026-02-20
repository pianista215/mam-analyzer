from math import sqrt
from typing import List, Optional, Tuple

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from mam_analyzer.models.flight_context import AirportContext, Runway, RunwayEnd
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.utils.units import compute_bearing, haversine, heading_within_range, latlon_to_xy


def _runway_utm_zone(runway: Runway) -> int:
    """Compute a single UTM zone from the runway midpoint to avoid zone-boundary issues."""
    mid_lon = (runway.ends[0].longitude + runway.ends[1].longitude) / 2
    return int((mid_lon + 180) // 6) + 1


def build_runway_polygon(runway: Runway, margin_width_m: float = 0, extend_m: float = 0):
    """Build a Shapely polygon representing the runway footprint in UTM coordinates.

    Uses both RunwayEnd positions to create a buffered rectangle.
    If extend_m > 0, the centreline is extended in both directions.
    Returns (polygon, utm_zone) so callers can project points in the same zone.
    """
    utm_zone = _runway_utm_zone(runway)
    e1, e2 = runway.ends[0], runway.ends[1]
    p1 = latlon_to_xy(e1.latitude, e1.longitude, utm_zone)
    p2 = latlon_to_xy(e2.latitude, e2.longitude, utm_zone)

    line = LineString([p1, p2])

    if extend_m > 0:
        (x1, y1), (x2, y2) = p1, p2
        dx = x2 - x1
        dy = y2 - y1
        length = sqrt(dx * dx + dy * dy)
        if length > 0:
            ux, uy = dx / length, dy / length
            p1_ext = (x1 - ux * extend_m, y1 - uy * extend_m)
            p2_ext = (x2 + ux * extend_m, y2 + uy * extend_m)
            line = LineString([p1_ext, p2_ext])

    half_width = runway.width_m / 2 + margin_width_m
    return line.buffer(half_width, cap_style=2), utm_zone


def build_runway_safe_zone(
    runway: Runway,
    margin_width_m: float = 15,
    turn_zone_radius_m: float = 100,
) -> BaseGeometry:
    """Build a safe zone that includes the runway polygon plus turn circles at each end."""
    polygon, utm_zone = build_runway_polygon(runway, margin_width_m)

    e1, e2 = runway.ends[0], runway.ends[1]
    p1 = latlon_to_xy(e1.latitude, e1.longitude, utm_zone)
    p2 = latlon_to_xy(e2.latitude, e2.longitude, utm_zone)

    turn1 = Point(p1).buffer(turn_zone_radius_m)
    turn2 = Point(p2).buffer(turn_zone_radius_m)

    return unary_union([polygon, turn1, turn2])


def match_runway_end(
    airport: AirportContext,
    heading: int,
    lat: float,
    lon: float,
    heading_tolerance: int = 20,
    max_distance_m: float = 5000,
) -> Optional[Tuple[Runway, RunwayEnd]]:
    """Find the runway end that best matches the given heading and position.

    Returns the (Runway, RunwayEnd) with the smallest distance, or None.
    """
    best = None
    best_distance = max_distance_m

    for runway in airport.runways:
        for end in runway.ends:
            if heading_within_range(heading, end.true_heading_deg, heading_tolerance):
                dist = haversine(lat, lon, end.latitude, end.longitude)
                if dist < best_distance:
                    best_distance = dist
                    best = (runway, end)

    return best


def match_runway_by_track(
    airport: AirportContext,
    track_points: List[Tuple[float, float]],
    heading_tolerance: int = 30,
) -> Optional[Tuple[Runway, RunwayEnd]]:
    """Find the runway whose polygon is intersected by the ground track line.

    track_points is a list of (lat, lon) in chronological order (at least 2 points).
    The track bearing is computed from the first to the last point and used to select
    the correct runway end (direction). Returns (Runway, RunwayEnd) or None.
    """
    if len(track_points) < 2:
        return None

    track_bearing = compute_bearing(
        track_points[0][0], track_points[0][1],
        track_points[-1][0], track_points[-1][1],
    )

    for runway in airport.runways:
        utm_zone = _runway_utm_zone(runway)
        rwy_polygon, _ = build_runway_polygon(runway)
        xy_points = [latlon_to_xy(lat, lon, utm_zone) for lat, lon in track_points]
        track_line = LineString(xy_points)

        if rwy_polygon.intersects(track_line):
            for end in runway.ends:
                if heading_within_range(track_bearing, end.true_heading_deg, heading_tolerance):
                    return runway, end

    return None


def match_runway_for_takeoff(
    airport: AirportContext,
    events: List[FlightEvent],
    airborne_idx: int,
    airborne_event: FlightEvent,
    fallback_heading: int,
) -> Optional[Tuple[Runway, RunwayEnd]]:
    """Identify the runway used for takeoff.

    Builds a ground track from the last 2 location events before airborne plus the
    airborne event itself, then intersects it with runway polygons. Falls back to
    heading+distance matching if no intersection is found.
    """
    from mam_analyzer.utils.location import collect_location_events_before

    prev_events = collect_location_events_before(events, airborne_idx, 2)
    if prev_events:
        track_points = [(e.latitude, e.longitude) for e in prev_events]
        track_points.append((airborne_event.latitude, airborne_event.longitude))
        result = match_runway_by_track(airport, track_points)
        if result is not None:
            return result

    return match_runway_end(airport, fallback_heading, airborne_event.latitude, airborne_event.longitude)


def match_runway_for_landing(
    airport: AirportContext,
    events: List[FlightEvent],
    touch_idx: int,
    touch_event: FlightEvent,
    fallback_heading: int,
) -> Optional[Tuple[Runway, RunwayEnd]]:
    """Identify the runway used for landing.

    Builds a ground track from the touch event plus the next 2 location events,
    then intersects it with runway polygons. Falls back to heading+distance matching
    if no intersection is found.
    """
    from mam_analyzer.utils.location import collect_location_events_after

    next_events = collect_location_events_after(events, touch_idx, 2)
    if next_events:
        track_points = [(touch_event.latitude, touch_event.longitude)]
        track_points.extend([(e.latitude, e.longitude) for e in next_events])
        result = match_runway_by_track(airport, track_points)
        if result is not None:
            return result

    return match_runway_end(airport, fallback_heading, touch_event.latitude, touch_event.longitude)


def point_inside_runway(lat: float, lon: float, polygon, utm_zone=None) -> bool:
    """Check whether a lat/lon point falls inside a runway polygon (UTM)."""
    x, y = latlon_to_xy(lat, lon, utm_zone)
    return polygon.covers(Point(x, y))
