from mam_analyzer.models.flight_events import FlightEvent

def event_has_ias(e: FlightEvent) -> bool:
	return e.other_changes.get("IASKnots") is not None

def get_ias_as_int(e: FlightEvent) -> int:
	return int(e.other_changes.get("IASKnots"))

def event_has_gs(e: FlightEvent) -> bool:
	return e.other_changes.get("GSKnots") is not None

def get_gs_as_int(e: FlightEvent) -> int:
	return int(e.other_changes.get("GSKnots"))	
