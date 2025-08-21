from abc import ABC, abstractmethod
from datetime import datetime
from typing import List
from mam_analyzer.models.flight_events import FlightEvent

class Analyzer(ABC):
    @abstractmethod
    def analyze(
        self,
        events: List[FlightEvent],
        start_time: int,
        end_time: int
    ) -> dict:
        """
        Analyze the phase of flight that begins at `start_time` and ends at `end_time`,
        using the subset of `events` that occurred within this interval.

        Returns a dictionary with (name, value) pairs
        representing the metrics or results extracted from the analyzed phase.

        Example:
            {
                "Fuel consumed":"200"
                "Max VS", "-200 fpm"
            }
        """
        pass