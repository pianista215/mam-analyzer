from datetime import datetime
from typing import List, Tuple, Optional
from mam_analyzer.phases.base import PhaseDetector
from mam_analyzer.models import FlightEvent  # Asumo que ya tienes un modelo así


class FlightEvaluator:
    def __init__(self):
        self.detectors: List[PhaseDetector] = []
        self.results: List[Tuple[str, datetime, datetime]] = []

    def add_detector(self, detector: PhaseDetector):
        self.detectors.append(detector)

    def evaluate(self, events: List[FlightEvent]):
        self.results.clear()
        for detector in self.detectors:
            result = detector.detect(events)
            if result:
                self.results.append((detector.phase_name, *result))

    def get_results(self) -> List[Tuple[str, datetime, datetime]]:
        return self.results