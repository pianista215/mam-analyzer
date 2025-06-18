from mam_analyzer.evaluator import FlightEvaluator
from mam_analyzer.phases.takeoff import TakeoffPhaseDetector
from mam_analyzer.parser import parse_json_file

evaluator = FlightEvaluator()
evaluator.add_detector(TakeoffPhaseDetector())

events = load_flight_data("data/UHSH-UHMM-B350.json")
evaluator.evaluate(events)

for phase_name, start, end in evaluator.get_results():
    print(f"{phase_name}: {start} → {end}")