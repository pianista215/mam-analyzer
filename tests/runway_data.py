"""Shared runway data for integration tests with real flight files.

Heading and length are computed automatically from runway end coordinates.
Data sourced from the airport database.
"""
from math import atan2, sin, cos, radians, degrees

from mam_analyzer.models.flight_context import AirportContext, FlightContext, Runway, RunwayEnd
from mam_analyzer.utils.units import haversine


def _bearing(lat1, lon1, lat2, lon2):
    """Compute initial bearing (degrees) from point 1 to point 2."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    return round((degrees(atan2(x, y)) + 360) % 360)


def _rwy(designators, width_m, d1, lat1, lon1, dt1, sw1, d2, lat2, lon2, dt2, sw2):
    """Build a Runway computing heading and length from end coordinates."""
    return Runway(
        designators=designators,
        width_m=width_m,
        length_m=round(haversine(lat1, lon1, lat2, lon2)),
        ends=[
            RunwayEnd(
                designator=d1, latitude=lat1, longitude=lon1,
                true_heading_deg=_bearing(lat1, lon1, lat2, lon2),
                displaced_threshold_m=dt1, stopway_m=sw1,
            ),
            RunwayEnd(
                designator=d2, latitude=lat2, longitude=lon2,
                true_heading_deg=_bearing(lat2, lon2, lat1, lon1),
                displaced_threshold_m=dt2, stopway_m=sw2,
            ),
        ],
    )


AIRPORT_RUNWAYS = {
    "LEPA": [
        _rwy("06L/24R", 45,
             "06L", 39.5471472, 2.7107278, 0, 75,
             "24R", 39.5625034, 2.7431946, 70, 0),
        _rwy("06R/24L", 45.1,
             "06R", 39.5412502, 2.7317272, 410, 58,
             "24L", 39.5553389, 2.761525, 0, 60),
    ],
    "LEPP": [
        _rwy("15/33", 45,
             "15", 42.7795444, -1.6532528, 0, 0,
             "33", 42.7604537, -1.6393406, 500, 0),
    ],
    "LPMA": [
        _rwy("05/23", 45,
             "05", 32.6889722, -16.7848785, 150, 0,
             "23", 32.7068045, -16.7640141, 151, 0),
    ],
    "UHMA": [
        _rwy("01/19", 60,
             "01", 64.719761, 177.732322, 0, 75,
             "19", 64.750122, 177.751014, 0, 75),
    ],
    "UHPT": [
        _rwy("02/20", 35,
             "02", 60.3782393, 166.0214281, 0, 0,
             "20", 60.391136, 166.029228, 0, 0),
    ],
    "UHSH": [
        _rwy("13/31", 42,
             "13", 53.5202055, 142.8703381, 0, 0,
             "31", 53.5130984, 142.8913593, 0, 0),
    ],
    "PAOM": [
        _rwy("10/28", 45.7,
             "10", 64.5143186, -165.4681381, 0, 60,
             "28", 64.5087571, -165.4322327, 0, 63),
        _rwy("3/21", 45.7,
             "21", 64.519843, -165.4257438, 183, 60,
             "3", 64.507234, -165.451833, 180, 0),
    ],
    "LEBB": [
        _rwy("10/28", 45,
             "10", 43.3032513, -2.9359239, 0, 144,
             "28", 43.3012546, -2.912461, 560, 0),
        _rwy("12/30", 45.1,
             "12", 43.3063216, -2.9248768, 0, 67,
             "30", 43.2958426, -2.8962885, 459, 60),
    ],
    "LEMG": [
        _rwy("12/30", 45.1,
             "12", 36.6910753, -4.507827, 0, 190,
             "30", 36.6795648, -4.4805125, 0, 489),
        _rwy("13/31", 45.1,
             "13", 36.6845573, -4.5126253, 0, 75,
             "31", 36.6654027, -4.485814, 0, 75),
    ],
    "UHMM": [
        _rwy("10/28", 60,
             "10", 59.9117855, 150.6895723, 0, 80,
             "28", 59.910139, 150.751178, 0, 80),
    ],
    "PANC": [
        _rwy("15/33", 58,
             "15", 61.1997218, -150.0145266, 0, 120,
             "33", 61.1710187, -149.9984751, 144, 109),
        _rwy("7L/25R", 46,
             "25R", 61.1698112, -149.9483007, 0, 120,
             "7L", 61.169765, -150.0083333, 0, 116),
        _rwy("7R/25L", 61,
             "25L", 61.1678817, -149.9726428, 0, 65,
             "7R", 61.1678122, -150.0428651, 0, 185),
    ],
    "LEAS": [
        _rwy("11/29", 45.1,
             "11", 43.5666347, -6.0476039, 0, 50,
             "29", 43.5604911, -6.0216369, 0, 50),
    ],
    "ENRA": [
        _rwy("14/32", 29.9,
             "14", 66.3667714, 14.295313, 33, 0,
             "32", 66.3608049, 14.307915, 34, 0),
    ],
    "ENDU": [
        _rwy("10/28", 45.1,
             "10", 69.0595061, 18.5098973, 442, 275,
             "28", 69.0523648, 18.5678437, 0, 271),
    ],
    "LEVD": [
        _rwy("05/23", 45,
             "05", 41.6970069, -4.8647728, 0, 205,
             "23", 41.7159859, -4.8389997, 0, 0),
        _rwy("14/32", 50,
             "14", 41.713262, -4.8619373, 0, 0,
             "32", 41.7066812, -4.8554363, 0, 0),
    ],
    "KEUG": [
        _rwy("16L/34R", 45.7,
             "16L", 44.1329639, -123.2027553, 0, 60,
             "34R", 44.1165089, -123.2025103, 0, 60),
        _rwy("16R/34L", 45.7,
             "16R", 44.135439, -123.2191743, 0, 60,
             "34L", 44.11347, -123.2188413, 0, 60),
    ],
    "EFKS": [
        _rwy("12/30", 45.1,
             "12", 65.995058, 29.219022, 40, 60,
             "30", 65.9799479, 29.2599721, 0, 60),
    ],
    "EFVA": [
        _rwy("16/34", 48,
             "16", 63.061994, 21.7543989, 0, 0,
             "34", 63.0405845, 21.7687031, 0, 200),
    ],
    "ENNA": [
        _rwy("16/34", 45.1,
             "16", 70.081247, 24.970575, 91, 0,
             "34", 70.056378, 24.976403, 92, 0),
    ],
    "ENTC": [
        _rwy("18/36", 45,
             "18", 69.6937907, 18.9258948, 388, 150,
             "36", 69.6723736, 18.9116177, 56, 145),
    ],
    "ESNX": [
        _rwy("12/30", 45,
             "12", 65.5985444, 19.2561694, 0, 60,
             "30", 65.5846556, 19.2987376, 0, 0),
    ],
    "EETN": [
        _rwy("08/26", 45,
             "08", 59.4133341, 24.8057382, 248, 0,
             "26", 59.4131721, 24.8672002, 0, 0),
    ],
    "OOMS": [
        _rwy("08L/26R", 60,
             "08L", 23.6058906, 58.2579432, 0, 121,
             "26R", 23.609037, 58.2970518, 165, 116),
        _rwy("08R/26L", 45.1,
             "08R", 23.5916528, 58.2669004, 418, 62,
             "26L", 23.5944631, 58.3018865, 0, 61),
    ],
    "LTFM": [
        _rwy("16L/34R", 46,
             "16L", 41.2986274, 28.7092527, 0, 0,
             "34R", 41.2648674, 28.7099245, 0, 0),
        _rwy("16R/34L", 60,
             "16R", 41.2986054, 28.706745, 0, 0,
             "34L", 41.2648427, 28.7074203, 0, 0),
        _rwy("17L/35R", 60,
             "17L", 41.2988302, 28.727038, 0, 0,
             "35R", 41.261919, 28.7277552, 0, 0),
        _rwy("17R/35L", 45,
             "17R", 41.2987973, 28.7245312, 0, 0,
             "35L", 41.2618904, 28.7252518, 0, 0),
        _rwy("18/36", 45,
             "18", 41.2897918, 28.7561756, 0, 60,
             "36", 41.2622421, 28.7567149, 0, 60),
    ],
    "EFKI": [
        _rwy("07/25", 48,
             "07", 64.283448, 27.6668714, 0, 0,
             "25", 64.2875149, 27.7178487, 0, 0),
    ],
    "CYBL": [
        _rwy("12/30", 46,
             "12", 49.9583121, -125.2827559, 0, 19,
             "30", 49.9457533, -125.2632638, 0, 0),
    ],
    "LEBL": [
        _rwy("02/20", 45.1,
             "02", 41.2877316, 2.0848197, 0, 0,
             "20", 41.3092875, 2.0946638, 0, 71),
        _rwy("06L/24R", 60,
             "06L", 41.2932451, 2.0672749, 430, 0,
             "24R", 41.305726, 2.103729, 0, 159),
        _rwy("06R/24L", 60,
             "06R", 41.2823122, 2.07435, 0, 63,
             "24L", 41.2922205, 2.103281, 0, 62),
    ],
}


def get_airport_context(icao, with_runways=True):
    """Create an AirportContext, optionally without runways."""
    runways = AIRPORT_RUNWAYS.get(icao, []) if with_runways else []
    return AirportContext(icao=icao, runways=runways)


def make_flight_context(departure_icao, landing_icao, with_runways=True):
    """Create a FlightContext for testing with the given airports."""
    return FlightContext(
        departure=get_airport_context(departure_icao, with_runways),
        destination=get_airport_context(landing_icao, with_runways),
        landing=get_airport_context(landing_icao, with_runways),
    )
