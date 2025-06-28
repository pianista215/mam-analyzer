from math import isclose

def heading_within_range(h1: int, h2: int, tolerance: int = 6) -> bool:
    """Returns True if the headings are within the specified ±tolerance degrees."""
    diff = abs((h1 - h2 + 180) % 360 - 180)
    return diff <= tolerance


def coords_differ(a: float, b: float, tolerance: float = 1e-6) -> bool:
    return not isclose(a, b, abs_tol=tolerance)    