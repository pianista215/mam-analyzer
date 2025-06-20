

def heading_within_range(h1: float, h2: float, tolerance: float = 8) -> bool:
    """Returns True if the headings are within the specified ±tolerance degrees."""
    diff = abs((h1 - h2 + 180) % 360 - 180)
    return diff <= tolerance