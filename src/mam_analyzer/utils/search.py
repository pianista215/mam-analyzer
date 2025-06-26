from typing import Callable, Optional, Sequence, Tuple, TypeVar
from datetime import datetime
from mam_analyzer.models.flight_events import FlightEvent

T = TypeVar("T", bound=FlightEvent)

def find_first_index_forward(
	events: Sequence[T],
	condition: Callable[[T], bool],
	from_time: Optional[datetime] = None,
	to_time: Optional[datetime] = None,
) -> Optional[Tuple[int, T]]:
	# Detect the first event that match the condition iterating forward
	for idx,event in enumerate(events):
		ts = event.timestamp

		if from_time is None or ts >= from_time:
			if to_time is None or ts <= to_time:
				if condition(event):
					return idx, event
			else:
				break

	return None

def find_first_index_forward_starting_from_idx(
	events: Sequence[T],
	start_idx: int,
	condition: Callable[[T], bool],
	from_time: Optional[datetime] = None,
	to_time: Optional[datetime] = None,
) -> Optional[Tuple[int, T]]:
	# Detect the first event that match the condition iterating forward
	for idx in range(start_idx,len(events)):
		event = events[idx]
		ts = event.timestamp

		if from_time is None or ts >= from_time:
			if to_time is None or ts <= to_time:
				if condition(event):
					return idx, event
			else:
				break

	return None	


def find_first_index_backward(
	events: Sequence[T],
	condition: Callable[[T], bool],
	from_time: Optional[datetime] = None,
	to_time: Optional[datetime] = None,
) -> Optional[Tuple[int, T]]:
	# Detect the first event that match the condition iterating backward
	for idx in range(len(events) - 1, -1, -1):
		event = events[idx]
		ts = event.timestamp

		if to_time is None or ts <= to_time:
			if from_time is None or ts >= from_time:
				if condition(event):
					return idx, event
			else:
				break

	return None

def find_first_index_backward_starting_from_idx(
	events: Sequence[T],
	start_idx: int,
	condition: Callable[[T], bool],
	from_time: Optional[datetime] = None,
	to_time: Optional[datetime] = None,
) -> Optional[Tuple[int, T]]:
	# Detect the first event that match the condition iterating backward
	for idx in range(start_idx, -1, -1):
		event = events[idx]
		ts = event.timestamp

		if to_time is None or ts <= to_time:
			if from_time is None or ts >= from_time:
				if condition(event):
					return idx, event
			else:
				break

	return None	
