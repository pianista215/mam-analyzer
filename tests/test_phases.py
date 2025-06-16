import json
import os
from datetime import datetime
import pytest

from src.mam_analyzer.phases import detect_engine_start_phase, parse_timestamp

def test_detect_engine_start_phase_synthetic():
    events = [
        {"Timestamp": "2025-06-14T17:00:00.1234567", "Changes": {"Latitude": "39,000", "Longitude": "2,000"}},
        {"Timestamp": "2025-06-14T17:01:00.23478", "Changes": {"Squawk": "1234"}},
        {"Timestamp": "2025-06-14T17:02:00.3234679", "Changes": {"Flaps": "49"}},
        {"Timestamp": "2025-06-14T17:03:00.1267", "Changes": {"Latitude": "39,001", "Longitude": "2,000"}},
    ]

    result = detect_engine_start_phase(events)
    assert result is not None
    start, end = result
    assert start == parse_timestamp("2025-06-14T17:00:00.1234567")
    assert end == parse_timestamp("2025-06-14T17:03:00.1267")

@pytest.mark.parametrize("filename", [
    "LEPA-LEPP-737.json",
    "LEPP-LEMG-737.json",
    "LPMA-Circuits-737.json",
    "UHMA-PAOM-B350.json",
    "UHPT-UHMA-B350.json",
    "UHPT-UHMA-SF34.json",
    "UHSH-UHMM-B350.json",
])    
def test_detect_engine_start_phase_from_real_files(filename):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    events = data["Events"]
    result = detect_engine_start_phase(events)

    assert result is not None, f"Puesta en marcha no detectada en {filename}"
    start, end = result
    assert isinstance(start, datetime)
    assert isinstance(end, datetime)
    assert start <= end
