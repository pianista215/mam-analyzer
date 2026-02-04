import json
import pytest
from pathlib import Path

from mam_analyzer.evaluator import FlightEvaluator
from mam_analyzer.parser import load_flight_data
from mam_analyzer.phases.analyzers.issues import Issues
from mam_analyzer.utils.parsing import parse_timestamp

DATA_DIR = Path("data")

@pytest.mark.parametrize(
    "filename, expected_metrics, expected_issues",
    [
        (
            "UHSH-UHMM-B350.json",
            [
                ("block_time_minutes","113"),
                ("airborne_time_minutes", "105"),
                ("initial_fob_kg", "1635"),
                ("fuel_consumed_kg", "515"),
                ("distance_nm", "484")
            ],
            [],
        ),
        (
            "LEPA-LEPP-737.json",
            [
                ("block_time_minutes","79"),
                ("airborne_time_minutes", "64"),
                ("initial_fob_kg", "6400"),
                ("fuel_consumed_kg", "3215"),
                ("distance_nm", "348")
            ],
            ['AppHighVsBelow1000AGL'],
        ),
        (
            "UHPT-UHMA-SF34.json",
            [
                ("block_time_minutes","127"),
                ("airborne_time_minutes", "117"),
                ("initial_fob_kg", "1673"),
                ("fuel_consumed_kg", "897"),
                ("distance_nm", "462")
            ],
            [],
        ),
        (
            "PAOM-PANC-B350-fromtaxi.json",
            [
                ("airborne_time_minutes", "111"),
                ("initial_fob_kg", "1010"),
                ("fuel_consumed_kg", "622"),
                ("distance_nm", "475")
            ],
            [],
        ),
        (
            "UHPT-UHMA-B350.json",
            [
                ("block_time_minutes","117"),
                ("airborne_time_minutes", "104"),
                ("initial_fob_kg", "1553"),
                ("fuel_consumed_kg", "525"),
                ("distance_nm", "423")
            ],
            [],
        ),
        (
            "UHMA-PAOM-B350.json",
            [
                ("block_time_minutes","115"),
                ("airborne_time_minutes", "108"),
                ("initial_fob_kg", "1049"),
                ("fuel_consumed_kg", "638"),
                ("distance_nm", "478")
            ],
            [],
        ),
        (
            "LEBB-touchgoLEXJ-LEAS.json",
            [
                ("airborne_time_minutes", "57"),
                ("initial_fob_kg", "166"),
                ("fuel_consumed_kg", "72"),
                ("distance_nm", "139")
            ],
            ['AppHighVsBelow1000AGL'],
        ),
        (
            "LPMA-Circuits-737.json",
            [
                ("airborne_time_minutes", "26"),
                ("initial_fob_kg", "9535"),
                ("fuel_consumed_kg", "1300"),
                ("distance_nm", "77")
            ],
            ['LandingHardFpm', 'AppHighVsBelow1000AGL'],
        ),
        (
            "LEPP-LEMG-737.json",
            [
                ("block_time_minutes","85"),
                ("airborne_time_minutes", "79"),
                ("initial_fob_kg", "6600"),
                ("fuel_consumed_kg", "3530"),
                ("distance_nm", "453")
            ],
            [],
        ),
        (
            "LEVD-fast-crash.json",
            [
                ("airborne_time_minutes", "2"),
                ("initial_fob_kg", "79"),
                ("fuel_consumed_kg", "33"), # Fuel refueled
                ("distance_nm", "3") 
            ],
            [
                'AirborneAllEnginesStopped',
                'LandingAllEnginesStopped',
                'LandingHardFpm',
                'TaxiOverspeed',
                'AppHighVsBelow1000AGL',
                'Refueling'
            ],
        ),
        (
            "zfw.json",
            [
                ("airborne_time_minutes", "288"),
                ("block_time_minutes", "311"),
                ("distance_nm", "1998"),
                ("fuel_consumed_kg", "30279"),
                ("initial_fob_kg", "34995"),
                ("zfw_kg", "188104")
            ],
            [],
        ),  
        (
            "zfw_modified.json",
            [
                ("airborne_time_minutes", "288"),
                ("block_time_minutes", "311"),
                ("distance_nm", "1998"),
                ("fuel_consumed_kg", "30279"),
                ("initial_fob_kg", "34995"),
                ("zfw_kg", "188104")
            ],
            ["ZfwModified"],
        ), 
    ],
)
def test_evaluator(filename, expected_metrics, expected_issues):
    file_path = DATA_DIR / filename
    events = load_flight_data(file_path)
    evaluator = FlightEvaluator()

    result = evaluator.evaluate(events)

    metrics = result.global_metrics

    assert len(metrics) == len(expected_metrics)

    expected_dict = dict(expected_metrics)

    for key, expected_value in expected_dict.items():
        assert key in metrics
        assert str(metrics[key]) == expected_value

    def has_issue(phases, code: str) -> bool:
        return any(
            issue.code == code
            for p in phases
            for issue in p.analysis.issues
        )        

    detected_issues = {
        issue.code
        for p in result.phases
        for issue in p.analysis.issues
    }

    expected_set = set(expected_issues)

    assert detected_issues == expected_set, (
        f"Issues mismatch for {filename}: "
        f"expected {expected_set}, got {detected_issues}"
    )

@pytest.mark.parametrize(
    "filename, expected_refuel_events",
    [
        (
            "LEVD-fast-crash.json",
            [
                {"phase": "takeoff", "timestamp": "2025-09-16T17:21:18.8514859", "value": "32"},
            ]
        ),
        (
            "UHSH-UHMM-B350.json",
            []
        ),
        (
            "UHPT-UHMA-B350.json",
            []
        ),
        (
            "LEBB-touchgoLEXJ-LEAS.json",
            []
        ),
        (
            "ENRA_ENDU_False_refueling.json",
            []
        ),
        (
            "CYBL_KEUG_REFUELING.json",
            [
                {"phase": "approach", "timestamp": "2025-09-19T01:56:36.3020965", "value": "398"},
            ]
        ),
    ]
)
def test_refueling_detection(filename, expected_refuel_events):
    file_path = DATA_DIR / filename
    events = load_flight_data(file_path)
    evaluator = FlightEvaluator()

    result = evaluator.evaluate(events)

    refuel_issues = []
    for phase in result.phases:
        for issue in phase.analysis.issues:
            if issue.code == Issues.ISSUE_REFUELING:
                refuel_issues.append({
                    "phase": phase.name.lower(),
                    "timestamp": issue.timestamp,
                    "value": issue.value,
                })

    assert len(refuel_issues) == len(expected_refuel_events), (
        f"{filename}: incorrect number of Refueling events.\n"
        f"Expected: {expected_refuel_events}\n"
        f"Detected: {refuel_issues}"
    )

    for expected, detected in zip(expected_refuel_events, refuel_issues):
        expected_timestamp = parse_timestamp(expected["timestamp"])
        expected_value = int(expected["value"])
        assert expected["phase"] == detected["phase"], (
            f"{filename}: wrong phase for refueling.\n"
            f"Expected: {expected['phase']}\n"
            f"Detected: {detected['phase']}"
        )

        assert expected_timestamp == detected["timestamp"], (
            f"{filename}: incorrect refueling timestamp.\n"
            f"Expected: {expected['timestamp']}\n"
            f"Detected: {detected['timestamp']}"
        )

        assert expected_value == int(detected["value"]), (
            f"{filename}: incorrect refueling value.\n"
            f"Expected: {expected['value']}\n"
            f"Detected: {detected['value']}"
        )