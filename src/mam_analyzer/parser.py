import json

from mam_analyzer.models.flight_events import FlightEvent

def load_flight_data(filepath):
	with open(filepath, "r", encoding="utf-8") as f:
		raw_json = json.load(f)
	raw_events = raw_json["Events"]
	return [FlightEvent.from_json(e) for e in raw_events]