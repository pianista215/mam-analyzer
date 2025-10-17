from math import isclose, radians, sin, cos, atan2, sqrt
from pyproj import CRS, Transformer

def heading_within_range(h1: int, h2: int, tolerance: int = 6) -> bool:
    """Returns True if the headings are within the specified ±tolerance degrees."""
    diff = abs((h1 - h2 + 180) % 360 - 180)
    return diff <= tolerance


def coords_differ(a: float, b: float, tolerance: float = 1e-6) -> bool:
    return not isclose(a, b, abs_tol=tolerance)

def haversine(lat1, lon1, lat2, lon2):
    # Earth radius in meters
    R = 6371000  
    
    # Coords to radians
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    
    # Haversine
    a = sin(dphi/2)**2 + cos(phi1) * cos(phi2) * sin(dlambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c

def meters_to_nm(meters: float) -> float:
    return meters / 1852

def latlon_to_xy(lat, lon):
    utm_zone = int((lon + 180) // 6) + 1
    hemisphere = "north" if lat >= 0 else "south"

    crs_utm = CRS.from_proj4(f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84 +units=m +no_defs")
    transformer = Transformer.from_crs("epsg:4326", crs_utm, always_xy=True)

    x, y = transformer.transform(lon, lat)
    return x, y    