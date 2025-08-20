from mam_analyzer.models.flight_events import FlightEvent

def event_has_location(e: FlightEvent) -> bool:
	return e.latitude is not None and e.longitude is not None