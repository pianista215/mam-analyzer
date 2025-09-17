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
                ("block_time_minutes","113")
            ],
        ),
        (
            "LEPA-LEPP-737.json",
            [
                ("block_time_minutes","79")
            ],
        ),
        (
            "UHPT-UHMA-SF34.json",
            [
                ("block_time_minutes","127")
            ],
        ),
        (
            "PAOM-PANC-B350-fromtaxi.json",
            [
            ],
        ),
        (
            "UHPT-UHMA-B350.json",
            [
                ("block_time_minutes","117")
            ],
        ),
        (
            "UHMA-PAOM-B350.json",
            [
                ("block_time_minutes","115")
            ],
        ),
        (
            "LEBB-touchgoLEXJ-LEAS.json",
            [
            ],
        ),
        (
            "LPMA-Circuits-737.json",
            [
            ],
        ),
        (
            "LEPP-LEMG-737.json",
            [
                ("block_time_minutes","85")
            ],
        ),
        (
            "LEVD-fast-crash.json",
            [            
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
