from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from mam_analyzer.context import FlightDetectorContext

class Detector(ABC):
    phase_name: str 

    @abstractmethod
    def detect(
        self,
        events: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
        context: FlightDetectorContext
    ) -> Optional[Tuple[datetime, datetime]]:
        """Detect phase between `start_time` and `end_time` from `events`.
        Return (start, end) or None if phase is not detected."""
        pass