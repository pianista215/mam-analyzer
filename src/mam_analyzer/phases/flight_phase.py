from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from mam_analyzer.models.flight_events import FlightEvent

@dataclass
class FlightPhase():
    name: str
    start: datetime
    end: datetime
    analysis: dict
    # TODO: add penalties/failures
    events: List[FlightEvent]

    def contains(self, event: FlightEvent) -> bool:
        """Return True if the event happens in this flight phase."""
        return self.start <= event.timestamp <= self.end

    def __str__(self):
        return f"{self.name}: {self.start} → {self.end}"