from mam_analyzer.models.flight_events import FlightEvent

def event_has_on_ground(e: FlightEvent) -> bool:
	return e.on_ground is not None

def is_on_ground(e: FlightEvent) -> bool:
	return e.on_ground is True

def is_on_air(e: FlightEvent)->bool:
    return e.on_ground is False