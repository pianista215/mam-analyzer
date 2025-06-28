from typing import List

from mam_analyzer.models.flight_events import FlightEvent

# This utils doesn't check if the event is full.
# Because MamAcars will track only changes in some events, 
# ensure to only use this functions in full events.

def get_engine_status(e: FlightEvent) -> List[str]:
	if not e.is_full_event():
		raise ValueError(f"Engine status only work with full events: {e}")

	result = []
	for k,v in e.other_changes.items():
		if k.startswith("Engine ") and k[7:].isdigit() and 1 <= int(k[7:]) <= 4:
			result.append(v)
	return result

def all_engines_are_on(e: FlightEvent) -> bool:
	return all_engines_are_on_from_status(get_engine_status(e))

def all_engines_are_on_from_status(status: List[str]) -> bool:
	return all(state == "On" for state in status)	

def all_engines_are_off(e: FlightEvent) -> bool:
	return all_engines_are_off_from_status(get_engine_status(e))

def all_engines_are_off_from_status(status: List[str]) -> bool:
	return all(state == "Off" for state in status)		

def some_engine_is_on(e: FlightEvent) -> bool:
	return some_engine_is_on_from_status(get_engine_status(e))

def some_engine_is_on_from_status(status: List[str]) -> bool:
	return any(state == "On" for state in status)

def some_engine_is_off(e: FlightEvent)-> bool:
	return some_engine_is_off_from_status(get_engine_status(e))

def some_engine_is_off_from_status(status: List[str])-> bool:
	return any(state == "Off" for state in status)	













