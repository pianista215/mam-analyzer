from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.flight_phase import FlightPhase
from mam_analyzer.phases.analyzers.analyzer import Analyzer
from mam_analyzer.phases.analyzers.approach import ApproachAnalyzer
from mam_analyzer.phases.analyzers.cruise import CruiseAnalyzer
from mam_analyzer.phases.analyzers.final_landing import FinalLandingAnalyzer
from mam_analyzer.phases.analyzers.takeoff import TakeoffAnalyzer
from mam_analyzer.phases.analyzers.touch_go import TouchAndGoAnalyzer
from mam_analyzer.phases.detectors.cruise import CruiseDetector
from mam_analyzer.phases.detectors.detector import Detector
from mam_analyzer.phases.detectors.final_landing import FinalLandingDetector
from mam_analyzer.phases.detectors.shutdown import ShutdownDetector
from mam_analyzer.phases.detectors.startup import StartupDetector
from mam_analyzer.phases.detectors.takeoff import TakeoffDetector
from mam_analyzer.phases.detectors.touch_go import TouchAndGoDetector

class PhasesAggregator:
    def __init__(self) -> None:
        self.detectors = {
            "startup": (StartupDetector(), None),
            "shutdown": (ShutdownDetector(), None),
            "takeoff": (TakeoffDetector(), TakeoffAnalyzer()),
            "touch_go": (TouchAndGoDetector(), TouchAndGoAnalyzer()),
            "final_landing": (FinalLandingDetector(), FinalLandingAnalyzer()),
            "cruise": (CruiseDetector(), CruiseAnalyzer()),
        }
        # Approach only has analyzer
        self.approach_analyzer = ApproachAnalyzer()

    def __filter_events(
        self,
        events: List[FlightEvent],
        start: datetime,
        end: datetime
    ) -> List[FlightEvent]:
        filtered = []
        for ev in events:
            if ev.timestamp >= start:
                if ev.timestamp <= end:
                    filtered.append(ev)
                else:
                    break
        return filtered

    def __generate_phase(
        self,
        events: List[FlightEvent],
        name: str,
        start: datetime,
        end: datetime,
        analyzer: Optional[Analyzer]
    ) -> FlightPhase:
        filtered_events = self.__filter_events(events, start, end)

        analysis = analyzer.analyze(filtered_events, start, end) if analyzer else {}

        return FlightPhase(name, start, end, analysis, filtered_events)

        
    def __get_touch_go_phases(
        self, 
        events: List[FlightEvent],
        takeoff_end: datetime, 
        landing_start: datetime,
    ) -> List[FlightPhase]:        
        result = []
        curr_start = takeoff_end

        detector, analyzer = self.detectors["touch_go"]

        while curr_start < landing_start:
            found_touch_go = detector.detect(
                events, 
                curr_start, 
                landing_start, 
            )

            if found_touch_go is None:
                curr_start = landing_start

            else:
                tg_start, tg_end = found_touch_go
                touch_go_phase = self.__generate_phase(events, "touch_go", tg_start, tg_end, analyzer)
                result.append(touch_go_phase)
                curr_start = tg_end

        return result

    def _generate_approach(
        self, 
        events: List[FlightEvent], 
        touch_phase: FlightPhase
    )-> FlightPhase:
        if touch_phase.name not in {"final_landing", "touch_go"}:
            raise RuntimeError("Final landing or touch_go expected to generate approach")

        # Approach starts 3 minutes before touch
        app_start = touch_phase.start + timedelta(seconds=-180)
        app_phase = self.__generate_phase(events, "approach", app_start, touch_phase.start, self.approach_analyzer)
        return app_phase 

    def identify_phases(self, events: List[FlightEvent])-> List[FlightPhase]:
        result: List[FlightPhase] = []

        # === Takeoff & Landing detection ===
        takeoff_detector, takeoff_analyzer = self.detectors["takeoff"]
        landing_detector, landing_analyzer = self.detectors["final_landing"]

        # First check that the flight has takeoff and landing
        _takeoff = takeoff_detector.detect(events, None, None)

        if _takeoff is None:
            raise RuntimeError("Can't identify takeoff phase")

        _landing = landing_detector.detect(events, None, None)

        if _landing is None:
            raise RuntimeError("Can't identify landing phase")

        _takeoff_start, _takeoff_end = _takeoff
        _landing_start, _landing_end = _landing

        _takeoff_phase = self.__generate_phase(events, "takeoff", _takeoff_start, _takeoff_end, takeoff_analyzer)

        # TODO: Rename in all the code final_landing for landing?
        _landing_phase = self.__generate_phase(events, "final_landing",_landing_start, _landing_end, landing_analyzer)
        
        # === Startup / Taxi before takeoff ===
        startup_detector, _ = self.detectors["startup"]
        _startup = startup_detector.detect(events, None, None)

        if _startup is None:
            first_timestamp = events[0].timestamp

            if first_timestamp != _takeoff_start:
                result.append(self.__generate_phase(events, "taxi", first_timestamp, _takeoff_start, None))

        else:
            _startup_start, _startup_end = _startup
            _startup_phase = self.__generate_phase(events, "startup", _startup_start, _startup_end, None)
            result.append(_startup_phase)

            if _startup_end != _takeoff_start:
                result.append(self.__generate_phase(events, "taxi", _startup_end, _takeoff_start, None))

        result.append(_takeoff_phase)

        # === Touch and goes + Cruise ===

        # Generate cruise between takeoff and touch_goes apps and final_landing apps

        _touch_go_phases = self.__get_touch_go_phases(
            events, 
            _takeoff_end, 
            _landing_start,
        )

        # Generate last approach for final_landing
        _last_landing_app = self._generate_approach(events, _landing_phase)

        cruise_detector, cruise_analyzer = self.detectors["cruise"]
        
        if len(_touch_go_phases) == 0:   
            
            found_cruise = cruise_detector.detect(
                events,
                _takeoff_end,
                _last_landing_app.start
            )

            if found_cruise is not None:
                cruise_start, cruise_end = found_cruise
                cruise_phase = self.__generate_phase(events, "cruise", cruise_start, cruise_end, cruise_analyzer)
                result.append(cruise_phase)

        else:
            look_for_cruise_start = _takeoff_end

            for _touch_go in _touch_go_phases:

                _touch_go_app = self._generate_approach(events, _touch_go)
                
                found_cruise = cruise_detector.detect(
                    events,
                    look_for_cruise_start,
                    _touch_go_app.start
                )
                if found_cruise is not None:
                    cruise_start, cruise_end = found_cruise
                    cruise_phase = self.__generate_phase(events, "cruise", cruise_start, cruise_end, cruise_analyzer)
                    result.append(cruise_phase)

                result.append(_touch_go_app)
                result.append(_touch_go)
                look_for_cruise_start = _touch_go.end

            # Add cruise part from last_touch_go to last_landing_app start
            found_cruise = cruise_detector.detect(
                events,
                look_for_cruise_start,
                _last_landing_app.start
            )
            if found_cruise is not None:
                cruise_start, cruise_end = found_cruise
                cruise_phase = self.__generate_phase(events, "cruise", cruise_start, cruise_end, cruise_analyzer)
                result.append(cruise_phase)

        # Once cruise and touch and goes apps are computed, add app and landing
        # === Final approach + landing ===
        result.append(_last_landing_app)
        result.append(_landing_phase)

        # === Shutdown / Taxi after landing ===
        shutdown_detector, _ = self.detectors["shutdown"]
        _shutdown = shutdown_detector.detect(events, None, None)

        if _shutdown is None:
            last_timestamp = events[len(events) - 1].timestamp

            if _landing_end != last_timestamp:
                result.append(self.__generate_phase(events, "taxi", _landing_end, last_timestamp, None))

        else:
            _shutdown_start, _shutdown_end = _shutdown
            _shutdown_phase = self.__generate_phase(events, "shutdown", _shutdown_start, _shutdown_end, None)

            if _landing_end != _shutdown_start:
                result.append(self.__generate_phase(events, "taxi", _landing_end, _shutdown_start, None))

            result.append(_shutdown_phase)

        for phase in result:
            print(phase)

        return result


