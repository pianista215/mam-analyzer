from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.analyzers.cruise import CruiseAnalyzer
from mam_analyzer.utils.parsing import parse_timestamp


def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)

@pytest.fixture
def analyzer():
    return CruiseAnalyzer()

def test_basic_cruise(analyzer):
    base = datetime(2025, 7, 5, 10, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=10)
    events = []

    start_event = make_event(base, Altitude=20050, FuelKg="6599,9924")

    events.append(start_event)

    for i in range(20):
        delta = timedelta(seconds=(i + 1) * 30)
        if i % 2 == 0:
            events.append(make_event(base + delta, Altitude=19900))
        else:
            events.append(make_event(base + delta, Altitude=20150))


    end_event = make_event(base + timedelta(seconds=40 * 30), Altitude=20050, FuelKg="6400,125")
    events.append(end_event)    

    result = analyzer.analyze(events, 0, len(events))
    assert result is not None
    assert result[0] == ('Fuel', 200)
    assert result[1] == ('CommonAlt', 20000)
    assert result[2] == ('HighAlt', 20000)

def test_multiple_altitude_on_cruise(analyzer):
    base = datetime(2025, 7, 5, 10, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=10)
    events = []

    start_event = make_event(base, Altitude=20050, FuelKg="6599,9924")

    events.append(start_event)

    for i in range(40):
        delta = timedelta(seconds=(i + 1) * 30)
        if i <10 :
            alt = 20100 + i
        elif i >=10 and i <= 35:
            alt = 24000 + i
        else:
            alt = 20100 + i
        events.append(make_event(base + delta, Altitude=alt))


    end_event = make_event(base + timedelta(seconds=41 * 30), Altitude=20050, FuelKg="5984,204")
    events.append(end_event)   
    print(events) 

    result = analyzer.analyze(events, 0, len(events))
    assert result is not None
    print(result)
    assert result[0] == ('Fuel', 616)
    assert result[1] == ('CommonAlt', 24000)
    assert result[2] == ('HighAlt', 24000)    
