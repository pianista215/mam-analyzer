from mam_analyzer.models.flight_events import FlightEvent

def event_has_landing_vs_fpm(e: FlightEvent) -> bool:
	return e.other_changes.get("LandingVSFpm") is not None

def get_landing_vs_fpm_as_int(e: FlightEvent) -> int:
	return int(e.other_changes.get("LandingVSFpm"))

def is_hard_landing(e: FlightEvent) -> bool:
	return get_landing_vs_fpm_as_int(e) < -450	