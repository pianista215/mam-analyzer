from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.result import AnalysisResult

@dataclass
class FlightPhase():
    name: str
    start: datetime
    end: datetime
    analysis: AnalysisResult
    events: List[FlightEvent]

    def contains(self, event: FlightEvent) -> bool:
        """Return True if the event happens in this flight phase."""
        return self.start <= event.timestamp <= self.end

    def is_airborne_phase(self) -> bool:
        # Consider unknown as climb and descend for now are "unknown"
        return self.name == "unknown" or self.name == "cruise" or self.name == "approach"

    def __str__(self):
        return f"{self.name}: {self.start} → {self.end}"

    def to_dict(self) -> dict:
        """Serialize this phase to a JSON-friendly dict."""
        return {
            "name": self.name,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "analysis": self.analysis.to_dict(),
            "events": [ev.to_dict() for ev in self.events],  # assumes FlightEvent has to_dict()
        }