from math import sqrt
from typing import Optional, Tuple

from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from mam_analyzer.models.flight_context import AirportContext, Runway, RunwayEnd
from mam_analyzer.utils.units import haversine, heading_within_range, latlon_to_xy


def build_runway_polygon(runway: Runway, margin_width_m: float = 0, extend_m: float = 0):
    """Build a Shapely polygon representing the runway footprint in UTM coordinates.

    Uses both RunwayEnd positions to create a buffered rectangle.
    If extend_m > 0, the centreline is extended in both directions.
    """
    e1, e2 = runway.ends[0], runway.ends[1]
    p1 = latlon_to_xy(e1.latitude, e1.longitude)
    p2 = latlon_to_xy(e2.latitude, e2.longitude)

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
    return line.buffer(half_width, cap_style=2)


def build_runway_safe_zone(
    runway: Runway,
    margin_width_m: float = 15,
    turn_zone_radius_m: float = 100,
) -> BaseGeometry:
    """Build a safe zone that includes the runway polygon plus turn circles at each end."""
    polygon = build_runway_polygon(runway, margin_width_m)

    e1, e2 = runway.ends[0], runway.ends[1]
    p1 = latlon_to_xy(e1.latitude, e1.longitude)
    p2 = latlon_to_xy(e2.latitude, e2.longitude)

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


def point_inside_runway(lat: float, lon: float, polygon) -> bool:
    """Check whether a lat/lon point falls inside a runway polygon (UTM)."""
    x, y = latlon_to_xy(lat, lon)
    return polygon.covers(Point(x, y))
