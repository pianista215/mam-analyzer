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

    result = analyzer.analyze(events, events[0].timestamp, events[len(events)- 1].timestamp)
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

    result = analyzer.analyze(events, events[0].timestamp, events[len(events)- 1].timestamp)
    assert result is not None
    assert result[0] == ('Fuel', 616)
    assert result[1] == ('CommonAlt', 24000)
    assert result[2] == ('HighAlt', 24000)    

def test_high_altitude_differs_from_common(analyzer):
    base = datetime(2025, 7, 5, 12, 0, 0)
    events = []

    # Start fuel
    events.append(make_event(base, Altitude=20020, FuelKg="5000"))

    # 15 min at FL200
    for i in range(30):
        events.append(make_event(base + timedelta(seconds=(i+1)*30), Altitude=20020))

    # 5 min at FL260
    for i in range(10):
        events.append(make_event(base + timedelta(seconds=(30+i+1)*30), Altitude=25980))

    # End fuel
    events.append(make_event(base + timedelta(minutes=20), Altitude=20020, FuelKg="4800"))

    result = analyzer.analyze(events, events[0].timestamp, events[len(events)- 1].timestamp)
    assert result is not None
    assert result[0] == ('Fuel', 200)
    assert result[1] == ('CommonAlt', 20000)
    assert result[2] == ('HighAlt', 26000)

def test_intermediate_fuel_changes_are_ignored(analyzer):
    base = datetime(2025, 7, 5, 16, 0, 0)
    events = []

    # Start with initial fuel
    events.append(make_event(base, Altitude=20000, FuelKg="7000"))

    # Intermediate events
    for i in range(1, 6):
        delta = timedelta(minutes=i)
        fuel_val = 7000 - (i * 50)
        events.append(make_event(base + delta, Altitude=20000, FuelKg=str(fuel_val)))

    # Last fuel event
    events.append(make_event(base + timedelta(minutes=10), Altitude=20000, FuelKg="6500"))

    result = analyzer.analyze(events, events[0].timestamp, events[len(events)- 1].timestamp)
    assert result is not None

    assert result[0] == ('Fuel', 500)
    assert result[1] == ('CommonAlt', 20000)
    assert result[2] == ('HighAlt', 20000)    

def test_missing_start_fuel_raises(analyzer):
    base = datetime(2025, 7, 5, 13, 0, 0)
    events = []

    # Without fuel in events
    for i in range(10):
        events.append(make_event(base + timedelta(seconds=i*30), Altitude=20000))

    with pytest.raises(RuntimeError, match="Can't retrieve start fuel event"):
        result = analyzer.analyze(events, events[0].timestamp, events[len(events)- 1].timestamp)   

def test_missing_altitudes_raises(analyzer):
    base = datetime(2025, 7, 5, 15, 0, 0)
    events = []

    events.append(make_event(base, FuelKg="6000"))

    # Without altitudes
    for i in range(10):
        events.append(make_event(base + timedelta(seconds=(i+1)*30), FuelKg="5990"))

    events.append(make_event(base + timedelta(minutes=5), FuelKg="5900"))

    with pytest.raises(RuntimeError, match="Can't retrieve most flown altitude or high altitude"):
        result = analyzer.analyze(events, events[0].timestamp, events[len(events)- 1].timestamp)


@pytest.mark.parametrize("filename, cruise_start, cruise_end, fuel, common, highest", [
    ("LEPA-LEPP-737.json", "2025-06-14T17:29:25.8916254", "2025-06-14T17:53:55.8771022", "904", "30000", "30000"),
    ("LEPP-LEMG-737.json", "2025-06-15T00:02:56.9507605", "2025-06-15T00:42:12.9611013", "1436", "33000", "33000"),
    ("UHMA-PAOM-B350.json", "2025-06-15T23:11:10.5834039", "2025-06-15T23:40:06.5834885", "134", "29000", "29000"),
    ("UHPT-UHMA-B350.json", "2025-06-15T18:33:34.8288609", "2025-06-15T19:31:56.8139074", "267", "28500", "28500"),
    ("UHPT-UHMA-SF34.json", "2025-06-05T13:19:55.2269445", "2025-06-05T14:28:41.2361792", "521", "23000", "23000"),
    ("UHSH-UHMM-B350.json", "2025-05-17T18:13:39.2464222", "2025-05-17T19:13:55.253485", "273", "29000", "29000"),
    ("PAOM-PANC-B350-fromtaxi.json", "2025-06-22T22:42:46.5642602", "2025-06-22T23:49:56.574365", "348", "27000", "27000"),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T22:48:17.3083458", "2025-07-04T23:04:23.315419", "17", "1000", "1500"),
    ("LEBB-touchgoLEXJ-LEAS.json", "2025-07-04T23:11:49.3157458", "2025-07-04T23:22:03.3293345", "15", "3000", "3000")
])
def test_cruise_analyzer_from_real_files(filename, cruise_start, cruise_end, fuel, common, highest, analyzer):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = analyzer.analyze(events, parse_timestamp(cruise_start), parse_timestamp(cruise_end))

    assert result[0] == ('Fuel', int(fuel))
    assert result[1] == ('CommonAlt', int(common))
    assert result[2] == ('HighAlt', int(highest))