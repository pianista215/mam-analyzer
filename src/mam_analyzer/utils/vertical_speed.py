from mam_analyzer.models.flight_events import FlightEvent

def event_has_vertical_speed(e: FlightEvent) -> bool:
	return e.other_changes.get("VSFpm") is not None

def get_vertical_speed_as_int(e: FlightEvent) -> int:
	return int(e.other_changes.get("VSFpm"))