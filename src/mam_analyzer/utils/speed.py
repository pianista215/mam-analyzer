from mam_analyzer.models.flight_events import FlightEvent

def event_has_ias(e: FlightEvent) -> bool:
	print("%s has ias knots %s" %(e, e.other_changes.get("IASKnots") is not None))
	return e.other_changes.get("IASKnots") is not None

def get_ias_as_int(e: FlightEvent) -> int:
	print("%s get ias knots: %s" % (e, int(e.other_changes.get("IASKnots"))))
	return int(e.other_changes.get("IASKnots"))	