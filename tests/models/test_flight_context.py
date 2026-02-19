from mam_analyzer.models.flight_context import FlightContext, AirportContext, Runway, RunwayEnd


def test_from_dict_full_context():
    data = {
        "departure": {
            "icao": "LEMD",
            "runways": [
                {
                    "designators": "14L/32R",
                    "width_m": 60.0,
                    "length_m": 4350.0,
                    "ends": [
                        {
                            "designator": "14L",
                            "latitude": 40.4936,
                            "longitude": -3.5668,
                            "true_heading_deg": 144.0,
                            "displaced_threshold_m": 0.0,
                            "stopway_m": 0.0,
                        },
                        {
                            "designator": "32R",
                            "latitude": 40.5200,
                            "longitude": -3.5900,
                            "true_heading_deg": 324.0,
                            "displaced_threshold_m": 0.0,
                            "stopway_m": 0.0,
                        },
                    ],
                }
            ],
        },
        "destination": {"icao": "LEBL"},
        "alternative1": {"icao": "LEZG"},
        "alternative2": {"icao": "LEVC"},
        "landing": {
            "icao": "LEBL",
            "runways": [
                {
                    "designators": "07L/25R",
                    "width_m": 60.0,
                    "length_m": 3352.0,
                    "ends": [
                        {
                            "designator": "07L",
                            "latitude": 41.2900,
                            "longitude": 2.0700,
                            "true_heading_deg": 70.0,
                        },
                        {
                            "designator": "25R",
                            "latitude": 41.2950,
                            "longitude": 2.1100,
                            "true_heading_deg": 250.0,
                        },
                    ],
                }
            ],
        },
    }

    ctx = FlightContext.from_dict(data)

    assert ctx.departure.icao == "LEMD"
    assert len(ctx.departure.runways) == 1
    assert ctx.departure.runways[0].designators == "14L/32R"
    assert ctx.departure.runways[0].width_m == 60.0
    assert len(ctx.departure.runways[0].ends) == 2
    assert ctx.departure.runways[0].ends[0].designator == "14L"
    assert ctx.departure.runways[0].ends[0].latitude == 40.4936
    assert ctx.departure.runways[0].ends[1].designator == "32R"

    assert ctx.destination.icao == "LEBL"
    assert ctx.alternative1.icao == "LEZG"
    assert ctx.alternative2.icao == "LEVC"
    assert ctx.landing.icao == "LEBL"
    assert len(ctx.landing.runways) == 1


def test_from_dict_nulls():
    data = {
        "departure": {"icao": "LEMD", "runways": []},
        "destination": {"icao": "LEBL"},
        "alternative1": None,
        "alternative2": None,
        "landing": None,
    }

    ctx = FlightContext.from_dict(data)

    assert ctx.departure.icao == "LEMD"
    assert ctx.departure.runways == []
    assert ctx.destination.icao == "LEBL"
    assert ctx.alternative1 is None
    assert ctx.alternative2 is None
    assert ctx.landing is None


def test_from_dict_only_alt1():
    data = {
        "departure": {"icao": "LEMD"},
        "destination": {"icao": "LEBL"},
        "alternative1": {"icao": "LEZG"},
        "landing": {"icao": "LEZG"},
    }

    ctx = FlightContext.from_dict(data)

    assert ctx.alternative1.icao == "LEZG"
    assert ctx.alternative2 is None
    assert ctx.landing.icao == "LEZG"
