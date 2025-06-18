from datetime import datetime
from dateutil import parser

def parse_coordinate(value: str) -> float:
    return float(value.replace(",", "."))

def parse_timestamp(ts: str) -> datetime:
    """Parses ISO 8601 timestamps with flexible fractional seconds."""
    return parser.isoparse(ts)