from mam_analyzer.models.flight_events import FlightEvent

def event_has_altitude(e: FlightEvent) -> bool:
	return e.other_changes.get("Altitude") is not None

def get_altitude_as_int(e: FlightEvent) -> int:
	return int(e.other_changes.get("Altitude"))

def get_altitude_as_int_rounded_to(e: FlightEvent, round_val: int) -> int: 
	return round(get_altitude_as_int(e) / round_val) * round_val