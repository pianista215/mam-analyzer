import pytest

from mam_analyzer.models.flight_events import FlightEvent

def make_event(changes: dict) -> FlightEvent:
    return FlightEvent.from_json({
        "Timestamp": "2025-01-01T12:00:00Z",
        "Changes": changes
    })


def test_has_started_engines_true_one_on():
    event = make_event({
        "Engine 1": "On",
        "Engine 2": "Off",
    })
    assert event.has_started_engines is True
    assert event.all_engines_started is False


def test_all_engines_started_true_multiple():
    event = make_event({
        "Engine 1": "On",
        "Engine 2": "On",
        "Engine 3": "On",
        "Engine 4": "On",
    })
    assert event.has_started_engines is True
    assert event.all_engines_started is True


def test_all_engines_started_false_partial_off():
    event = make_event({
        "Engine 1": "On",
        "Engine 2": "Off",
        "Engine 3": "On",
    })
    assert event.has_started_engines is True
    assert event.all_engines_started is False


def test_no_engines_keys():
    event = make_event({
        "Flaps": "10",
        "Gear": "Down",
    })
    assert event.has_started_engines is None
    assert event.all_engines_started is None


def test_ignores_non_numeric_engine_suffix():
    event = make_event({
        "Engine A": "On",  # Not valid
        "Engine B": "On",
    })
    assert event.has_started_engines is None
    assert event.all_engines_started is None


def test_ignores_out_of_range_engine_numbers():
    event = make_event({
        "Engine 5": "On",  # Out of 1-4
        "Engine 6": "On",
    })
    assert event.has_started_engines is None
    assert event.all_engines_started is None


def test_empty_changes_dict():
    event = make_event({})
    assert event.has_started_engines is None
    assert event.all_engines_started is None
