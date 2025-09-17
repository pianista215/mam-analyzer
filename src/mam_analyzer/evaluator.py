from typing import List, Dict, Any, Optional

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.phases_aggregator import PhasesAggregator
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.flight_report import FlightReport
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.search import find_first_index_forward
from mam_analyzer.utils.units import coords_differ



class FlightEvaluator:
    def __init__(self):
        self.aggregator = PhasesAggregator()

    def calculate_global_metrics(self, phases: List[FlightPhase])-> Dict[str, Any]:
        metrics: dict[str, Any] = {}

        if not phases:
            return metrics

        seconds = (phases[-1].end - phases[0].start).total_seconds()

        block_time = self.calculate_block_time(phases)

        if block_time is not None:
            metrics["block_time_minutes"] = block_time

        return metrics

    def evaluate(self, events: List[FlightEvent]) -> FlightReport:
        phases: List[FlightPhase] = self.aggregator.identify_phases(events)
        global_metrics = self.calculate_global_metrics(phases)
        return FlightReport(phases=phases, global_metrics=global_metrics)

    def calculate_block_time(self, phases: List[FlightPhase]) -> Optional[int]:
        first_phase = phases[0]
        last_phase = phases[-1]

        if first_phase.name == 'startup' and last_phase.name == 'shutdown':
            first_event = first_phase.events[0]
            start_lat = first_event.latitude
            start_lon = first_event.longitude

            def eventDiffLocationStartup(e: FlightEvent) -> bool:
                return (
                    event_has_location(e) and 
                    (
                        coords_differ(e.latitude, start_lat) or
                        coords_differ(e.longitude, start_lon)
                    )
                )

            found_pushback = find_first_index_forward(
                first_phase.events,
                eventDiffLocationStartup,
                first_phase.start,
                first_phase.end
            )

            if found_pushback is None:
                # Consider start of blocktime the end of startup phase
                start_block_time = first_phase.end
            else:
                _, pushback_event = found_pushback
                start_block_time = pushback_event.timestamp            

            end_block_time = last_phase.start

            elapsed_seconds = (end_block_time - start_block_time).total_seconds()

            return round(elapsed_seconds/60)


        else:
            return None