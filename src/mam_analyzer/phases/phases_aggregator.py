from dataclasses import dataclass
from datetime import datetime
from typing import List

from mam_analyzer.detector import Detector
from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
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


class PhasesAggregator:
    def __init__(self) -> None:
        self.startup_detector = StartupDetector()
        self.takeoff_detector = TakeoffDetector()
        self.touch_go_detector = TouchAndGoDetector()
        self.final_landing_detector = FinalLandingDetector()
        self.shutdown_detector = ShutdownDetector()

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

        _touch_go_phases = self.__get_touch_go_phases(
            events, 
            _takeoff_end, 
            _landing_start,
            context
        )

        for _touch_go in _touch_go_phases:
            result.append(_touch_go)

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

        return result


