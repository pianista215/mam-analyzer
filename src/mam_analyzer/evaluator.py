from typing import List, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.phases_aggregator import PhasesAggregator
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.flight_report import FlightReport


class FlightEvaluator:
    def __init__(self):
        self.aggregator = PhasesAggregator()

    def calculate_global_metrics(self, phases: List[FlightPhase])-> Dict[str, Any]:
        metrics: dict[str, Any] = {}

        if not phases:
            return metrics

        metrics["duration_seconds"] = (phases[-1].end - phases[0].start).total_seconds()

        return metrics

    def evaluate(self, events: List[FlightEvent]) -> FlightReport:
        phases: List[FlightPhase] = self.aggregator.identify_phases(events)
        global_metrics = self.calculate_global_metrics(phases)
        return FlightReport(phases=phases, global_metrics=global_metrics)