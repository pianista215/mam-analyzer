from typing import List, Dict, Any, Optional

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.phases_aggregator import PhasesAggregator
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.phases.analyzers.issues import Issues
from mam_analyzer.phases.analyzers.result import AnalysisIssue
from mam_analyzer.flight_report import FlightReport
from mam_analyzer.utils.engines import all_engines_are_off, some_engine_is_off
from mam_analyzer.utils.fuel import event_has_fuel, get_fuel_kg_as_float
from mam_analyzer.utils.location import event_has_location
from mam_analyzer.utils.search import find_first_index_forward
from mam_analyzer.utils.units import coords_differ, haversine, meters_to_nm



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

        fuel_refueled = self.check_refueling(phases)

        fuel_consumed = self.calculate_consumed_fuel(initial_fob_kg, phases)
        metrics["fuel_consumed_kg"] = round(fuel_consumed + fuel_refueled)

        metrics["distance_nm"] = self.calculate_distance(phases)

        self.check_engine_stopped_in_flight(phases)

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
        if first_phase.name == "startup":
            for event in first_phase.events:
                if event_has_fuel(event):
                    fuel = get_fuel_kg_as_float(event)
                    if initial_fob < fuel :
                        initial_fob = fuel
        else:
            # First event has always all the data
            initial_fob = get_fuel_kg_as_float(first_phase.events[0])

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

    def calculate_distance(self, phases: List[FlightPhase]) -> int:
        distance_meters = 0.0
        last_lat = None
        last_lon = None

        for phase in phases:
            if phase.name != "startup" and phase.name != "taxi" and phase.name != "backtrack" and phase.name != "shutdown":
                for event in phase.events:
                    if event_has_location(event):
                        if last_lat is not None and last_lon is not None:
                            distance_meters += haversine(event.latitude, event.longitude, last_lat, last_lon)
                        last_lat = event.latitude
                        last_lon = event.longitude
                        
        return round(meters_to_nm(distance_meters))

    def check_refueling(self, phases: List[FlightPhase]) -> int:
        fuel_refueled = 0
        last_fuel = None
        # Check all phases except first phase
        for i in range(1, len(phases)):
            phase = phases[i]

            for event in phase.events:
                if event_has_fuel(event):
                    fuel_event_kg = get_fuel_kg_as_float(event)

                    # In some planes at shutdown some fuel come back to the container
                    if last_fuel is not None and (fuel_event_kg - last_fuel) > 2.0:
                        refueled_quantity = round(fuel_event_kg - last_fuel)
                        phase.analysis.issues.append(
                            AnalysisIssue(
                                code=Issues.ISSUE_REFUELING,
                                timestamp=event.timestamp,
                                value=refueled_quantity
                            )
                        )
                        fuel_refueled += refueled_quantity
                   
                    last_fuel = fuel_event_kg

        return fuel_refueled

    def check_engine_stopped_in_flight(self, phases: List[FlightPhase]):
        single_failure_detected = False

        for phase in phases:
            if phase.is_airborne_phase():
                for event in phase.events:
                    if event.is_full_event() and all_engines_are_off(event):
                        phase.analysis.issues.append(
                            AnalysisIssue(
                                code=Issues.ISSUE_AIRBORNE_ALL_ENGINES_STOPPED,
                                timestamp=event.timestamp,
                            )
                        )
                        return
                    elif some_engine_is_off(event) and not single_failure_detected:
                        phase.analysis.issues.append(
                            AnalysisIssue(
                                code=Issues.ISSUE_AIRBORNE_ENGINE_STOPPED,
                                timestamp=event.timestamp,
                            )
                        )
                        single_failure_detected = True




                        



