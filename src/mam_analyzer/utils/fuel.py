from mam_analyzer.models.flight_events import FlightEvent

def event_has_fuel(e: FlightEvent) -> bool:
	return e.other_changes.get("FuelKg") is not None

def get_fuel_kg_as_float(e: FlightEvent) -> float:
	return float(e.other_changes.get("FuelKg").replace(",", "."))