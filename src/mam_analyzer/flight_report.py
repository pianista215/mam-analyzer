from dataclasses import dataclass
from typing import List, Dict, Any

from mam_analyzer.phases.flight_phase import FlightPhase

@dataclass
class FlightReport:
    phases: List[FlightPhase]
    global_metrics: Dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "global": self.global_metrics,
            "phases": [p.to_dict() for p in self.phases],
        }
