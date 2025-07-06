from datetime import datetime, timedelta
import json
import os
import pytest

from mam_analyzer.context import FlightDetectorContext
from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.cruise import CruiseDetector
from mam_analyzer.utils.parsing import parse_timestamp


def make_event(timestamp, **changes):
    event_dict = {
        "Timestamp": timestamp.isoformat(timespec="microseconds"),
        "Changes": {k: str(v) for k, v in changes.items()},
    }
    return FlightEvent.from_json(event_dict)

@pytest.fixture
def detector():
    return CruiseDetector()

@pytest.fixture
def context():
    return FlightDetectorContext()

def test_no_cruise_due_to_low_agl_altitude(detector, context):
    base = datetime(2025, 7, 5, 10, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=10)
    events = [
        make_event(base + timedelta(seconds=i * 30), Altitude=2000, AGLAltitude=1000)
        for i in range(20)
    ]
    result = detector.detect(events, from_time, to_time, context)
    assert result is None    


def test_cruise_detected_above_10000_ft_agl(detector, context):
    base = datetime(2025, 7, 5, 11, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=10)
    events = list()

    for i in range(10):
        seconds = base + timedelta(seconds=i * 60)
        if i < 2:
            events.append(
                make_event(seconds, Altitude=21000, AGLAltitude=19000)
            )
        elif i < 5:
            events.append(
                make_event(seconds, Altitude = 25000, AGLAltitude = 23000) # start
            ) 
        elif i < 7:
            events.append(
                make_event(seconds, Altitude = 27000, AGLAltitude = 25000)
            )
        else:
            events.append(
                make_event(seconds, Altitude = 24000, AGLAltitude = 22000) # end
            )
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(minutes = 2)
    assert end == base + timedelta(minutes=10)


def test_cruise_detected_above_7000_ft_agl(detector, context):
    base = datetime(2025, 7, 5, 11, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=20)
    events = list()

    for i in range(20):
        seconds = base + timedelta(seconds=i * 60)
        if i < 2:
            events.append(
                make_event(seconds, Altitude=5000, AGLAltitude=4000)
            )
        elif i < 5:
            events.append(
                make_event(seconds, Altitude = 8000, AGLAltitude = 7000) # start
            ) 
        elif i < 14:
            events.append(
                make_event(seconds, Altitude = 9000, AGLAltitude = 8000) # end
            )
        else:
            events.append(
                make_event(seconds, Altitude = 5000, AGLAltitude = 4000) 
            )
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(minutes = 2)
    assert end == base + timedelta(minutes=13)

def test_cruise_detected_above_3000_ft_agl(detector, context):
    base = datetime(2025, 7, 5, 11, 0, 0)
    from_time = base
    to_time = base + timedelta(minutes=20)
    events = list()

    for i in range(20):
        seconds = base + timedelta(seconds=i * 60)
        if i < 2:
            events.append(
                make_event(seconds, Altitude=4500, AGLAltitude=2000) # start
            )
        elif i < 5:
            events.append(
                make_event(seconds, Altitude = 5500, AGLAltitude = 3500)
            ) 
        elif i < 14:
            events.append(
                make_event(seconds, Altitude = 4500, AGLAltitude = 2000)
            )
        else:
            events.append(
                make_event(seconds, Altitude = 5500, AGLAltitude = 3500) #end
            )
    start, end = detector.detect(events, from_time, to_time, context)
    assert start == base + timedelta(minutes = 0)
    assert end == base + timedelta(minutes=20) 


#Ensure always that from and to correspond with takeoff and touch_go or final_landing tests
@pytest.mark.parametrize(
    "filename, from_time, to_time, expected_start, expected_end", [
    (
        "LEPA-LEPP-737.json", 
        "2025-06-14T17:19:23.8899645", 
        "2025-06-14T18:22:03.8839814", 
        "2025-06-14T17:29:25.8916254", 
        "2025-06-14T17:53:55.8771022"
    ),
    (
        "LEPP-LEMG-737.json", 
        "2025-06-14T23:51:02.9812455", 
        "2025-06-15T01:08:58.9593068", 
        "2025-06-15T00:02:56.9507605", 
        "2025-06-15T00:42:12.9611013"
    ),
    (
        "LPMA-Circuits-737.json", 
        "2025-06-02T21:49:51.7385484", 
        "2025-06-02T22:13:43.7386248", 
        "None", 
        "None"
    ),
    (
        "UHMA-PAOM-B350.json", 
        "2025-06-15T22:20:50.577950", 
        "2025-06-16T00:07:26.5753238", 
        "2025-06-15T23:11:10.5834039", 
        "2025-06-15T23:40:06.5834885"
    ),
    (
        "UHPT-UHMA-B350.json", 
        "2025-06-15T18:18:16.828107", 
        "2025-06-15T20:01:00.8191063", 
        "2025-06-15T18:33:34.8288609", 
        "2025-06-15T19:31:56.8139074"
    ),
    (
        "UHPT-UHMA-SF34.json", 
        "2025-06-05T13:09:09.2296981", 
        "2025-06-05T15:05:21.2266523", 
        "2025-06-05T13:19:55.2269445", 
        "2025-06-05T14:28:41.2361792"
    ),
    (
        "UHSH-UHMM-B350.json", 
        "2025-05-17T17:57:09.2445871", 
        "2025-05-17T19:41:01.243375", 
        "2025-05-17T18:13:39.2464222", 
        "2025-05-17T19:13:55.253485"
    ),
    (
        "PAOM-PANC-B350-fromtaxi.json", 
        "2025-06-22T22:26:42.5590209", 
        "2025-06-23T00:15:48.5520445", 
        "2025-06-22T22:42:46.5642602", 
        "2025-06-22T23:49:56.574365"
    ),
    (
        "LEBB-touchgoLEXJ-LEAS.json", 
        "2025-07-04T22:48:17.3083458", 
        "2025-07-04T23:04:23.315419", 
        "2025-07-04T22:48:17.3083458", 
        "2025-07-04T23:04:23.315419"
    ),
    (
        "LEBB-touchgoLEXJ-LEAS.json", 
        "2025-07-04T23:08:17.3078436", 
        "2025-07-04T23:44:13.3164862", 
        "2025-07-04T23:11:49.3157458", 
        "2025-07-04T23:22:03.3293345"
    ),
])
def test_cruise_detects_from_real_files(
    filename, 
    from_time, 
    to_time, 
    expected_start, 
    expected_end, 
    detector, 
    context
):
    path = os.path.join("data", filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_events = data["Events"]
    events = [FlightEvent.from_json(e) for e in raw_events]
    result = detector.detect(events, parse_timestamp(from_time), parse_timestamp(to_time), context)

    if expected_start != 'None' and expected_end != 'None':
        assert result is not None, f"Cruise not detected in {filename}"
        start, end = result

        expected_start_dt = parse_timestamp(expected_start)
        expected_end_dt = parse_timestamp(expected_end)

        assert start == expected_start_dt, f"Incorrect start for cruise in {filename}"
        assert end == expected_end_dt, f"Incorrect end for cruise in {filename}"

    else:
        assert result is None, f"Cruise shouldn't been detected in {filename}"      