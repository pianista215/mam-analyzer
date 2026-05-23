from datetime import datetime
from typing import List, Dict, Any, Optional

from mam_analyzer.models.flight_context import FlightContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.analyzer import Analyzer
from mam_analyzer.phases.analyzers.issues import Issues
from mam_analyzer.phases.analyzers.result import AnalysisResult, AnalysisIssue
from mam_analyzer.utils.speed import event_has_gs, get_gs_as_int
from mam_analyzer.utils.units import haversine

PARAM_TAXI_POSITION = "taxi_position"
TAXI_PRE_TAKEOFF = "pre_takeoff"
TAXI_POST_LANDING = "post_landing"

_RUNWAY_EXEMPT_METERS = 100


def _collect_location_events(
    events: List[FlightEvent],
    start_time: datetime,
    end_time: datetime,
) -> List[FlightEvent]:
    """Return events within the time window that have valid lat/lon, in chronological order."""
    result = []
    for e in events:
        if e.timestamp >= start_time:
            if e.timestamp <= end_time:
                if e.latitude is not None and e.longitude is not None:
                    result.append(e)
            else:
                break
    return result


def _compute_pre_takeoff_exempt_from(
    loc_events: List[FlightEvent],
) -> Optional[datetime]:
    """
    Return the timestamp from which events are exempt from overspeed detection
    for a pre-takeoff taxi (last ~100 m before the runway entry).

    Works backwards from the last location event (closest to runway). When the
    accumulated distance from the end first reaches or exceeds _RUNWAY_EXEMPT_METERS,
    returns the timestamp of the event at that boundary — all events at or after
    that timestamp are within the last 100 m and are exempt.

    Returns None if there are fewer than two location events (distance cannot be
    computed), which means no exemption is applied.
    Returns the first location event's timestamp if the entire taxi is shorter
    than 100 m (exempt everything).
    """
    if len(loc_events) < 2:
        return None

    accumulated = 0.0
    n = len(loc_events)
    for i in range(n - 1, 0, -1):
        prev = loc_events[i - 1]
        curr = loc_events[i]
        dist = haversine(prev.latitude, prev.longitude, curr.latitude, curr.longitude)
        accumulated += dist
        if accumulated >= _RUNWAY_EXEMPT_METERS:
            # curr is within 100 m of the end; prev is >= 100 m from the end.
            # Exempt from curr.timestamp onwards.
            return curr.timestamp

    # Entire taxi is shorter than 100 m → exempt everything.
    return loc_events[0].timestamp


def _compute_post_landing_exempt_until(
    loc_events: List[FlightEvent],
) -> Optional[datetime]:
    """
    Return the timestamp until which events are exempt from overspeed detection
    for a post-landing taxi (first ~100 m after leaving the runway).

    Works forwards from the first location event (closest to runway). When the
    accumulated distance from the start first reaches or exceeds _RUNWAY_EXEMPT_METERS,
    returns the timestamp of the event at that boundary — all events at or before
    that timestamp are within the first 100 m and are exempt.

    Returns None if there are fewer than two location events.
    Returns the last location event's timestamp if the entire taxi is shorter
    than 100 m (exempt everything).
    """
    if len(loc_events) < 2:
        return None

    accumulated = 0.0
    n = len(loc_events)
    for i in range(n - 1):
        curr = loc_events[i]
        nxt = loc_events[i + 1]
        dist = haversine(curr.latitude, curr.longitude, nxt.latitude, nxt.longitude)
        accumulated += dist
        if accumulated >= _RUNWAY_EXEMPT_METERS:
            # curr is within 100 m of the start; nxt is >= 100 m from the start.
            # Exempt up to and including curr.timestamp.
            return curr.timestamp

    # Entire taxi is shorter than 100 m → exempt everything.
    return loc_events[-1].timestamp


class TaxiAnalyzer(Analyzer):
    def analyze(
        self,
        events: List[FlightEvent],
        start_time: datetime,
        end_time: datetime,
        context: Optional[FlightContext] = None,
        phase_params: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        """Analyze taxi phase generating:
           - Overspeed taxi issue

        When phase_params contains PARAM_TAXI_POSITION:
          - TAXI_PRE_TAKEOFF:  events in the last ~100 m (before runway entry)
                               are exempt from the overspeed check.
          - TAXI_POST_LANDING: events in the first ~100 m (after runway exit)
                               are exempt from the overspeed check.
        """

        result = AnalysisResult()

        taxi_position = phase_params.get(PARAM_TAXI_POSITION) if phase_params else None

        exempt_from: Optional[datetime] = None   # pre-takeoff: exempt at or after this ts
        exempt_until: Optional[datetime] = None  # post-landing: exempt at or before this ts

        if taxi_position == TAXI_PRE_TAKEOFF:
            loc_events = _collect_location_events(events, start_time, end_time)
            exempt_from = _compute_pre_takeoff_exempt_from(loc_events)

        elif taxi_position == TAXI_POST_LANDING:
            loc_events = _collect_location_events(events, start_time, end_time)
            exempt_until = _compute_post_landing_exempt_until(loc_events)

        for e in events:
            ts = e.timestamp
            if ts >= start_time:
                if ts <= end_time:
                    if event_has_gs(e):
                        gs = get_gs_as_int(e)

                        if gs > 30:
                            in_exempt_zone = (
                                (exempt_from is not None and ts >= exempt_from)
                                or (exempt_until is not None and ts <= exempt_until)
                            )

                            if not in_exempt_zone:
                                result.issues.append(
                                    AnalysisIssue(
                                        code=Issues.ISSUE_TAXI_OVERSPEED,
                                        timestamp=e.timestamp,
                                        value=gs
                                    )
                                )

                else:
                    break

        return result
