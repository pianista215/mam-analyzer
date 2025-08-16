from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent

class Detector(ABC):
    phase_name: str 

    @abstractmethod
    def detect(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime,
        context: FlightDetectorContext
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect phase between `start_time` and `end_time` from `events`.
        Return (start, end) or None if phase is not detected."""
        pass