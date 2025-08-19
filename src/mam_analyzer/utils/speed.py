from mam_analyzer.models.flight_events import FlightEvent

def event_has_ias(e: FlightEvent) -> bool:
	return e.other_changes.get("IASKnots") is not None

def get_ias_as_int(e: FlightEvent) -> int:
	return int(e.other_changes.get("IASKnots"))	