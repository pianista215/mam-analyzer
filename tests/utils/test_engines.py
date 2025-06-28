import pytest

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.utils.engines import get_engine_status,all_engines_are_on,all_engines_are_off,some_engine_is_on,some_engine_is_off

BASE_CHANGES_FULL_EVENT = {
    "Latitude": "32,69286",
    "Longitude": "-16,7776",
    "onGround": "True",
    "Altitude": "190",
    "AGLAltitude": "0",
    "Altimeter": "-74",
    "VSFpm": "0",
    "Heading": "140",
    "GSKnots": "0",
    "IASKnots": "0",
    "QNHSet": "1013",
    "Flaps": "0",
    "Gear": "Down",
    "FuelKg": "9535,299668470565",
    "Squawk": "2000",
    "AP": "Off",
}

def make_full_event(extra_changes: dict[str, str]) -> FlightEvent:
    changes = BASE_CHANGES_FULL_EVENT.copy()
    changes.update(extra_changes)
    return FlightEvent.from_json({
        "Timestamp": "2025-01-01T12:00:00Z",
        "Changes": changes,
    })

@pytest.fixture
def empty_event() -> FlightEvent:
    return make_full_event({})    

@pytest.fixture
def single_motor_on() -> FlightEvent:
    return make_full_event({"Engine 1": "On"})

@pytest.fixture
def single_motor_off() -> FlightEvent:
    return make_full_event({"Engine 1": "Off"})

@pytest.fixture
def multi_motor_all_on() -> FlightEvent:
    return make_full_event({"Engine 1": "On", "Engine 2": "On"})

@pytest.fixture
def multi_motor_all_off() -> FlightEvent:
    return make_full_event({"Engine 1": "Off", "Engine 2": "Off"})

@pytest.fixture
def multi_motor_mix_order1() -> FlightEvent:
    return make_full_event({"Engine 1": "Off", "Engine 2": "On"})

@pytest.fixture
def multi_motor_mix_order2() -> FlightEvent:
    return make_full_event({"Engine 1": "On", "Engine 2": "Off"})

def tests_functions_on_empty_event(empty_event):
    assert get_engine_status(empty_event) == []
    assert all_engines_are_on(empty_event) == True
    assert all_engines_are_off(empty_event) == True
    assert some_engine_is_on(empty_event) == False
    assert some_engine_is_off(empty_event) == False

def tests_functions_on_single_on(single_motor_on):
    assert get_engine_status(single_motor_on) == ["On"]
    assert all_engines_are_on(single_motor_on) == True
    assert all_engines_are_off(single_motor_on) == False
    assert some_engine_is_on(single_motor_on) == True
    assert some_engine_is_off(single_motor_on) == False

def tests_functions_on_single_off(single_motor_off):
    assert get_engine_status(single_motor_off) == ["Off"]
    assert all_engines_are_on(single_motor_off) == False
    assert all_engines_are_off(single_motor_off) == True
    assert some_engine_is_on(single_motor_off) == False
    assert some_engine_is_off(single_motor_off) == True       

def tests_functions_on_multi_all_on(multi_motor_all_on):
    assert get_engine_status(multi_motor_all_on) == ["On", "On"]
    assert all_engines_are_on(multi_motor_all_on) == True
    assert all_engines_are_off(multi_motor_all_on) == False
    assert some_engine_is_on(multi_motor_all_on) == True
    assert some_engine_is_off(multi_motor_all_on) == False

def tests_functions_on_multi_all_off(multi_motor_all_off):
    assert get_engine_status(multi_motor_all_off) == ["Off", "Off"]
    assert all_engines_are_on(multi_motor_all_off) == False
    assert all_engines_are_off(multi_motor_all_off) == True
    assert some_engine_is_on(multi_motor_all_off) == False
    assert some_engine_is_off(multi_motor_all_off) == True

def tests_functions_on_multi_mix(multi_motor_mix_order1, multi_motor_mix_order2):
    assert get_engine_status(multi_motor_mix_order1) == ["Off", "On"]
    assert get_engine_status(multi_motor_mix_order2) == ["On", "Off"]

    assert all_engines_are_on(multi_motor_mix_order1) == False
    assert all_engines_are_on(multi_motor_mix_order2) == False

    assert all_engines_are_off(multi_motor_mix_order1) == False
    assert all_engines_are_off(multi_motor_mix_order2) == False

    assert some_engine_is_on(multi_motor_mix_order1) == True
    assert some_engine_is_on(multi_motor_mix_order2) == True

    assert some_engine_is_off(multi_motor_mix_order1) == True
    assert some_engine_is_off(multi_motor_mix_order2) == True