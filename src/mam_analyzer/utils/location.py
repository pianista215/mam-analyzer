from typing import List

from mam_analyzer.models.flight_events import FlightEvent


def event_has_location(e: FlightEvent) -> bool:
    return e.latitude is not None and e.longitude is not None


def collect_location_events_before(
    events: List[FlightEvent], before_idx: int, count: int
) -> List[FlightEvent]:
    """Return up to `count` events with location found before `before_idx`, in chronological order."""
    collected = []
    for idx in range(before_idx - 1, -1, -1):
        if event_has_location(events[idx]):
            collected.append(events[idx])
            if len(collected) == count:
                break
    collected.reverse()
    return collected


def collect_location_events_after(
    events: List[FlightEvent], after_idx: int, count: int
) -> List[FlightEvent]:
    """Return up to `count` events with location found after `after_idx`, in chronological order."""
    collected = []
    for idx in range(after_idx + 1, len(events)):
        if event_has_location(events[idx]):
            collected.append(events[idx])
            if len(collected) == count:
                break
    return collected