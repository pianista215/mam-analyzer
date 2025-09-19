from typing import List, Dict, Any, Optional

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.phases_aggregator import PhasesAggregator
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.flight_report import FlightReport
from mam_analyzer.utils.fuel import event_has_fuel, get_fuel_kg_as_float
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

        metrics["airborne_time_minutes"] = self.calculate_airborne_time(phases)

        initial_fob_kg = self.calculate_initial_fob(phases[0])
        metrics["initial_fob_kg"] = round(initial_fob_kg)

        fuel_consumed = self.calculate_consumed_fuel(initial_fob_kg, phases)
        metrics["fuel_consumed_kg"] = round(fuel_consumed)

        return metrics

    def evaluate(self, events: List[FlightEvent]) -> FlightReport:
        phases: List[FlightPhase] = self.aggregator.identify_phases(events)
        global_metrics = self.calculate_global_metrics(phases)
        return FlightReport(phases=phases, global_metrics=global_metrics)

    def calculate_airborne_time(self, phases: List[FlightPhase]) -> int:
        start_airborne_time = None
        end_airborne_time = None

        for phase in phases:
            if phase.name == 'takeoff':
                start_airborne_time = phase.start
            elif phase.name == 'final_landing':
                end_airborne_time = phase.start

        elapsed_seconds = (end_airborne_time - start_airborne_time).total_seconds()
        return round(elapsed_seconds / 60)

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

    def calculate_initial_fob(self, first_phase: FlightPhase) -> float:
        initial_fob = 0
        for event in first_phase.events:
            if event_has_fuel(event):
                fuel = get_fuel_kg_as_float(event)
                if initial_fob < fuel :
                    initial_fob = fuel                

        return initial_fob

    def calculate_consumed_fuel(self, initial_fob: float, phases: List[FlightPhase]) -> float:
        last_fuel_event_kg = 0

        def look_for_fuel_event(phase: FlightPhase) -> float:
            fuel_event_kg = None
            for event in reversed(phase.events):
                if event_has_fuel(event):
                    fuel_event_kg = get_fuel_kg_as_float(event)
                    break
            return fuel_event_kg

        for phase in reversed(phases):
            last_fuel_event_kg = look_for_fuel_event(phase)
            if last_fuel_event_kg is not None:
                break

        return initial_fob - last_fuel_event_kg
