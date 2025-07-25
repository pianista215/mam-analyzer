from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from mam_analyzer.detector import Detector
from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.cruise import CruiseDetector
from mam_analyzer.phases.final_landing import FinalLandingDetector
from mam_analyzer.phases.shutdown import ShutdownDetector
from mam_analyzer.phases.startup import StartupDetector
from mam_analyzer.phases.takeoff import TakeoffDetector
from mam_analyzer.phases.touch_go import TouchAndGoDetector

@dataclass
class FlightPhase():
    name: str
    start: datetime
    end: datetime

    def contains(self, event: FlightEvent) -> bool:
        """Return True if the event happens in this flight phase."""
        return self.start <= event.timestamp <= self.end

    def __str__(self):
        return f"{self.name}: {self.start} → {self.end}"

class PhasesAggregator:
    def __init__(self) -> None:
        self.startup_detector = StartupDetector()
        self.takeoff_detector = TakeoffDetector()
        self.touch_go_detector = TouchAndGoDetector()
        self.final_landing_detector = FinalLandingDetector()
        self.shutdown_detector = ShutdownDetector()
        self.cruise_detector = CruiseDetector()

    def __get_touch_go_phases(
        self, 
        events: List[FlightEvent],
        takeoff_end: datetime, 
        landing_start: datetime,
        context: FlightDetectorContext
    ) -> List[FlightPhase]:        
        result = list()
        curr_start = takeoff_end

        while curr_start < landing_start:
            found_touch_go = self.touch_go_detector.detect(
                events, 
                curr_start, 
                landing_start, 
                context
            )

            if found_touch_go is None:
                curr_start = landing_start

            else:
                touch_go_start, touch_go_end = found_touch_go
                touch_go_phase = FlightPhase("touch_go", touch_go_start, touch_go_end)
                result.append(touch_go_phase)
                curr_start = touch_go_end

        return result

    def _generate_approach(self, touch_phase: FlightPhase)-> FlightPhase:
        if touch_phase.name != "final_landing" and touch_phase.name != "touch_go":
            raise RuntimeError("Final landing or touch_go expected to generate approach")

        # Approach starts 3 minutes before touch
        app_start = touch_phase.start + timedelta(seconds=-180)
        app_phase = FlightPhase("approach", app_start, touch_phase.start)
        return app_phase 


    def identify_phases(self, events: List[FlightEvent])-> List[FlightPhase]:
        context = FlightDetectorContext() # Not used for now
        result = list()

        # First check that the flight has takeoff and landing
        _takeoff = self.takeoff_detector.detect(events, None, None, context)

        if _takeoff is None:
            print("No takeoff found")
            return result

        _landing = self.final_landing_detector.detect(events, None, None, context)

        if _landing is None:
            print("No landing detected")
            return result

        _takeoff_start, _takeoff_end = _takeoff
        _landing_start, _landing_end = _landing

        _takeoff_phase = FlightPhase("takeoff", _takeoff_start, _takeoff_end)
        # TODO: Rename in all the code final_landing for landing?
        _landing_phase = FlightPhase("final_landing", _landing_start, _landing_end)

        _startup = self.startup_detector.detect(events, None, None, context)

        if _startup is None:
            first_timestamp = events[0].timestamp

            if first_timestamp != _takeoff_start:
                result.append(FlightPhase("taxi", first_timestamp, _takeoff_start))

        else:
            _startup_start, _startup_end = _startup
            _startup_phase = FlightPhase("startup", _startup_start, _startup_end)
            result.append(_startup_phase)

            if _startup_end != _takeoff_start:
                result.append(FlightPhase("taxi", _startup_end, _takeoff_start))

        result.append(_takeoff_phase)

        # Generate cruise between takeoff and touch_goes apps and final_landing apps

        _touch_go_phases = self.__get_touch_go_phases(
            events, 
            _takeoff_end, 
            _landing_start,
            context
        )

        # Generate last approach for final_landing
        _last_landing_app = self._generate_approach(_landing_phase)

        if len(_touch_go_phases) == 0:   
            
            found_cruise = self.cruise_detector.detect(
                events,
                _takeoff_end,
                _last_landing_app.start,
                context
            )

            if found_cruise is not None:
                cruise_start, cruise_end = found_cruise
                cruise_phase = FlightPhase("cruise", cruise_start, cruise_end)
                result.append(cruise_phase)

        else:
            look_for_cruise_start = _takeoff_end

            for _touch_go in _touch_go_phases:

                _touch_go_app = self._generate_approach(_touch_go)

                found_cruise = self.cruise_detector.detect(
                    events,
                    look_for_cruise_start,
                    _touch_go_app.start,
                    context
                )
                if found_cruise is not None:
                    cruise_start, cruise_end = found_cruise
                    cruise_phase = FlightPhase("cruise", cruise_start, cruise_end)
                    result.append(cruise_phase)

                result.append(_touch_go_app)
                result.append(_touch_go)
                look_for_cruise_start = _touch_go.end

            # Add cruise part from last_touch_go to last_landing_app start
            found_cruise = self.cruise_detector.detect(
                events,
                look_for_cruise_start,
                _last_landing_app.start,
                context
            )
            if found_cruise is not None:
                cruise_start, cruise_end = found_cruise
                cruise_phase = FlightPhase("cruise", cruise_start, cruise_end)
                result.append(cruise_phase)

        # Once cruise and touch and goes apps are computed, add app and landing
        result.append(_last_landing_app)
        result.append(_landing_phase)

        _shutdown = self.shutdown_detector.detect(events, None, None, context)

        if _shutdown is None:
            last_timestamp = events[len(events) - 1].timestamp

            if _landing_end != last_timestamp:
                result.append(FlightPhase("taxi", _landing_end, last_timestamp))

        else:
            _shutdown_start, _shutdown_end = _shutdown
            _shutdown_phase = FlightPhase("shutdown", _shutdown_start, _shutdown_end)

            if _landing_end != _shutdown_start:
                result.append(FlightPhase("taxi", _landing_end, _shutdown_start))

            result.append(_shutdown_phase)

        for phase in result:
            print(phase)

        return result


