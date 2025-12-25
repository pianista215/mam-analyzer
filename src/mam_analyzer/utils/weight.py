from mam_analyzer.models.flight_events import FlightEvent

def event_has_zfw(e: FlightEvent) -> bool:
	return e.other_changes.get("ZFW") is not None

def get_zfw_as_int(e: FlightEvent) -> int:
	return int(e.other_changes.get("ZFW"))