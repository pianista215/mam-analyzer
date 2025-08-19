from mam_analyzer.models.flight_events import FlightEvent

def event_has_on_ground(e: FlightEvent) -> bool:
	return e.other_changes.get("onGround") is not None

def is_on_ground(e: FlightEvent) -> bool:
	return e.other_changes.get("onGround") == "True"