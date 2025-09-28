from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.result import AnalysisResult

class Analyzer(ABC):
    @abstractmethod
    def analyze(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime
    ) -> AnalysisResult:
        """
        Analyze the phase of flight that begins at `start_time` and ends at `end_time`,
        using the subset of `events` that occurred within this interval.

        Returns a Analysis results where part is dictionary with (name, value) pairs
        representing the metrics or results extracted from the analyzed phase and the
        other part are the issues found in the phase (Ex taxi overspeed)

        Example:
            {
                "Fuel consumed":"200"
                "Max VS", "-200 fpm"
            }
        """
        pass