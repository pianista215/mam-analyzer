from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class RunwayEnd:
    designator: str
    latitude: float
    longitude: float
    true_heading_deg: float
    displaced_threshold_m: float
    stopway_m: float
    max_glideslope_deg: Optional[float] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RunwayEnd":
        return RunwayEnd(
            designator=data["designator"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            true_heading_deg=data["true_heading_deg"],
            displaced_threshold_m=data.get("displaced_threshold_m", 0.0),
            stopway_m=data.get("stopway_m", 0.0),
            max_glideslope_deg=data.get("max_glideslope_deg"),
        )


@dataclass
class Runway:
    designators: str
    width_m: float
    length_m: float
    ends: List[RunwayEnd]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Runway":
        return Runway(
            designators=data["designators"],
            width_m=data["width_m"],
            length_m=data["length_m"],
            ends=[RunwayEnd.from_dict(e) for e in data.get("ends", [])],
        )


@dataclass
class AirportContext:
    icao: str
    runways: List[Runway] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AirportContext":
        return AirportContext(
            icao=data["icao"],
            runways=[Runway.from_dict(r) for r in data.get("runways", [])],
        )


@dataclass
class FlightContext:
    departure: AirportContext
    destination: AirportContext
    alternative1: Optional[AirportContext] = None
    alternative2: Optional[AirportContext] = None
    landing: Optional[AirportContext] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FlightContext":
        alt1_data = data.get("alternative1")
        alt2_data = data.get("alternative2")
        landing_data = data.get("landing")

        return FlightContext(
            departure=AirportContext.from_dict(data["departure"]),
            destination=AirportContext.from_dict(data["destination"]),
            alternative1=AirportContext.from_dict(alt1_data) if alt1_data else None,
            alternative2=AirportContext.from_dict(alt2_data) if alt2_data else None,
            landing=AirportContext.from_dict(landing_data) if landing_data else None,
        )
