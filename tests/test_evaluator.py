import json
import pytest
from pathlib import Path

from mam_analyzer.evaluator import FlightEvaluator
from mam_analyzer.parser import load_flight_data
from mam_analyzer.utils.parsing import parse_timestamp

DATA_DIR = Path("data")

@pytest.mark.parametrize(
    "filename, expected_metrics",
    [
        (
            "UHSH-UHMM-B350.json",
            [
                ("block_time_minutes","113"),
                ("airborne_time_minutes", "105"),
                ("initial_fob_kg", "1635")
            ],
        ),
        (
            "LEPA-LEPP-737.json",
            [
                ("block_time_minutes","79"),
                ("airborne_time_minutes", "64"),
                ("initial_fob_kg", "6400")
            ],
        ),
        (
            "UHPT-UHMA-SF34.json",
            [
                ("block_time_minutes","127"),
                ("airborne_time_minutes", "117"),
                ("initial_fob_kg", "1673")
            ],
        ),
        (
            "PAOM-PANC-B350-fromtaxi.json",
            [
                ("airborne_time_minutes", "111"),
                ("initial_fob_kg", "1010")
            ],
        ),
        (
            "UHPT-UHMA-B350.json",
            [
                ("block_time_minutes","117"),
                ("airborne_time_minutes", "104"),
                ("initial_fob_kg", "1553")
            ],
        ),
        (
            "UHMA-PAOM-B350.json",
            [
                ("block_time_minutes","115"),
                ("airborne_time_minutes", "108"),
                ("initial_fob_kg", "1049")
            ],
        ),
        (
            "LEBB-touchgoLEXJ-LEAS.json",
            [
                ("airborne_time_minutes", "57"),
                ("initial_fob_kg", "166")
            ],
        ),
        (
            "LPMA-Circuits-737.json",
            [
                ("airborne_time_minutes", "26"),
                ("initial_fob_kg", "9535")
            ],
        ),
        (
            "LEPP-LEMG-737.json",
            [
                ("block_time_minutes","85"),
                ("airborne_time_minutes", "79"),
                ("initial_fob_kg", "6600")
            ],
        ),
        (
            "LEVD-fast-crash.json",
            [
                ("airborne_time_minutes", "2"),
                ("initial_fob_kg", "79")    
            ],
        ),
    ],
)
def test_evaluator(filename, expected_metrics):
    file_path = DATA_DIR / filename
    events = load_flight_data(file_path)
    evaluator = FlightEvaluator()

    metrics = evaluator.evaluate(events).global_metrics

    assert len(metrics) == len(expected_metrics)

    expected_dict = dict(expected_metrics)

    for key, expected_value in expected_dict.items():
        assert key in metrics
        assert str(metrics[key]) == expected_value
