from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.analyzer import Analyzer
from mam_analyzer.phases.analyzers.issues import Issues
from mam_analyzer.phases.analyzers.result import AnalysisResult, AnalysisIssue
from mam_analyzer.utils.speed import event_has_gs, get_gs_as_int

class TaxiAnalyzer(Analyzer):
    def analyze(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime
    ) -> AnalysisResult:
        """Analyze taxi phase generating:
           - Overspeed taxi issue
        """

        result = AnalysisResult()

        for e in events:
            ts = e.timestamp
            if ts >= start_time:
                if ts <= end_time:
                    if event_has_gs(e):
                        ias = get_gs_as_int(e)

                        if ias > 25:
                            result.issues.append(
                                AnalysisIssue(
                                    code=Issues.ISSUE_TAXI_OVERSPEED,
                                    timestamp=e.timestamp,
                                    value=ias
                                )
                            )

                else:
                    break        

        return result