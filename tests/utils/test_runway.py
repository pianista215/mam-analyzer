import pytest
from shapely.geometry import Point

from mam_analyzer.models.flight_context import AirportContext, Runway, RunwayEnd
from mam_analyzer.utils.runway import (
    build_runway_polygon,
    build_runway_safe_zone,
    match_runway_end,
    point_inside_runway,
)
from mam_analyzer.utils.units import latlon_to_xy


def _make_runway(
    lat1=39.5517, lon1=2.7388,
    lat2=39.5365, lon2=2.7279,
    heading1=244, heading2=64,
    designator1="24L", designator2="06R",
    width_m=45, length_m=3270,
):
    """Create a Runway for testing (defaults based on LEPA 24L/06R)."""
    return Runway(
        designators=f"{designator1}/{designator2}",
        width_m=width_m,
        length_m=length_m,
        ends=[
            RunwayEnd(
                designator=designator1,
                latitude=lat1, longitude=lon1,
                true_heading_deg=heading1,
                displaced_threshold_m=0, stopway_m=0,
            ),
            RunwayEnd(
                designator=designator2,
                latitude=lat2, longitude=lon2,
                true_heading_deg=heading2,
                displaced_threshold_m=0, stopway_m=0,
            ),
        ],
    )


# === build_runway_polygon ===

class TestBuildRunwayPolygon:
    def test_polygon_contains_both_ends(self):
        rwy = _make_runway()
        poly, utm_zone = build_runway_polygon(rwy)

        p1 = Point(latlon_to_xy(rwy.ends[0].latitude, rwy.ends[0].longitude, utm_zone))
        p2 = Point(latlon_to_xy(rwy.ends[1].latitude, rwy.ends[1].longitude, utm_zone))

        assert poly.covers(p1)
        assert poly.covers(p2)

    def test_point_far_away_is_outside(self):
        rwy = _make_runway()
        poly, utm_zone = build_runway_polygon(rwy)

        far_point = Point(latlon_to_xy(40.0, 3.0, utm_zone))
        assert not poly.covers(far_point)

    def test_margin_makes_polygon_bigger(self):
        rwy = _make_runway()
        poly_no_margin, _ = build_runway_polygon(rwy, margin_width_m=0)
        poly_with_margin, _ = build_runway_polygon(rwy, margin_width_m=20)

        assert poly_with_margin.area > poly_no_margin.area

    def test_extend_makes_polygon_longer(self):
        rwy = _make_runway()
        poly_no_extend, _ = build_runway_polygon(rwy, extend_m=0)
        poly_with_extend, _ = build_runway_polygon(rwy, extend_m=500)

        assert poly_with_extend.area > poly_no_extend.area

    def test_polygon_width_is_correct(self):
        rwy = _make_runway(width_m=60)
        poly, utm_zone = build_runway_polygon(rwy, margin_width_m=0, extend_m=0)

        p1 = latlon_to_xy(rwy.ends[0].latitude, rwy.ends[0].longitude, utm_zone)
        p2 = latlon_to_xy(rwy.ends[1].latitude, rwy.ends[1].longitude, utm_zone)
        centreline = Point((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)

        # Centre should be inside
        assert poly.covers(centreline)


# === build_runway_safe_zone ===

class TestBuildRunwaySafeZone:
    def test_safe_zone_is_bigger_than_polygon(self):
        rwy = _make_runway()
        poly, _ = build_runway_polygon(rwy, margin_width_m=15)
        safe = build_runway_safe_zone(rwy, margin_width_m=15, turn_zone_radius_m=100)

        assert safe.area > poly.area

    def test_safe_zone_contains_runway_ends(self):
        rwy = _make_runway()
        safe = build_runway_safe_zone(rwy)

        _, utm_zone = build_runway_polygon(rwy)
        p1 = Point(latlon_to_xy(rwy.ends[0].latitude, rwy.ends[0].longitude, utm_zone))
        p2 = Point(latlon_to_xy(rwy.ends[1].latitude, rwy.ends[1].longitude, utm_zone))

        assert safe.covers(p1)
        assert safe.covers(p2)


# === match_runway_end ===

class TestMatchRunwayEnd:
    def test_matches_correct_end_by_heading(self):
        rwy = _make_runway()
        airport = AirportContext(icao="LEPA", runways=[rwy])

        # Heading close to 244 => should match 24L end
        result = match_runway_end(airport, heading=242, lat=39.5517, lon=2.7388)
        assert result is not None
        matched_rwy, matched_end = result
        assert matched_end.designator == "24L"

    def test_matches_opposite_end(self):
        rwy = _make_runway()
        airport = AirportContext(icao="LEPA", runways=[rwy])

        # Heading close to 64 => should match 06R end
        result = match_runway_end(airport, heading=62, lat=39.5365, lon=2.7279)
        assert result is not None
        _, matched_end = result
        assert matched_end.designator == "06R"

    def test_no_match_if_heading_too_far(self):
        rwy = _make_runway()
        airport = AirportContext(icao="LEPA", runways=[rwy])

        result = match_runway_end(airport, heading=180, lat=39.5517, lon=2.7388)
        assert result is None

    def test_no_match_if_too_far_away(self):
        rwy = _make_runway()
        airport = AirportContext(icao="LEPA", runways=[rwy])

        # Far away position
        result = match_runway_end(airport, heading=244, lat=41.0, lon=2.0)
        assert result is None

    def test_no_runways_returns_none(self):
        airport = AirportContext(icao="LEPA", runways=[])
        result = match_runway_end(airport, heading=244, lat=39.5517, lon=2.7388)
        assert result is None

    def test_picks_closest_when_multiple_runways(self):
        rwy1 = _make_runway(
            lat1=39.5517, lon1=2.7388,
            lat2=39.5365, lon2=2.7279,
            heading1=244, heading2=64,
            designator1="24L", designator2="06R",
        )
        rwy2 = _make_runway(
            lat1=39.5600, lon1=2.7500,
            lat2=39.5450, lon2=2.7400,
            heading1=244, heading2=64,
            designator1="24R", designator2="06L",
        )
        airport = AirportContext(icao="LEPA", runways=[rwy1, rwy2])

        # Position close to rwy1 end1
        result = match_runway_end(airport, heading=244, lat=39.5517, lon=2.7388)
        assert result is not None
        _, matched_end = result
        assert matched_end.designator == "24L"


# === point_inside_runway ===

class TestPointInsideRunway:
    def test_point_on_runway_is_inside(self):
        rwy = _make_runway()
        poly, utm_zone = build_runway_polygon(rwy)

        # Midpoint of the runway
        mid_lat = (rwy.ends[0].latitude + rwy.ends[1].latitude) / 2
        mid_lon = (rwy.ends[0].longitude + rwy.ends[1].longitude) / 2

        assert point_inside_runway(mid_lat, mid_lon, poly, utm_zone) is True

    def test_point_far_away_is_outside(self):
        rwy = _make_runway()
        poly, utm_zone = build_runway_polygon(rwy)

        assert point_inside_runway(40.0, 3.0, poly, utm_zone) is False

    def test_end_points_are_inside(self):
        rwy = _make_runway()
        poly, utm_zone = build_runway_polygon(rwy)

        assert point_inside_runway(rwy.ends[0].latitude, rwy.ends[0].longitude, poly, utm_zone) is True
        assert point_inside_runway(rwy.ends[1].latitude, rwy.ends[1].longitude, poly, utm_zone) is True
