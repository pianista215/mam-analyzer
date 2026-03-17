# Changelog

## [1.3.0] - 2026-03-17

- Increased taxi overspeed threshold from 25 to 30 knots

## [1.2.1] - 2026-02-20

- Fixed takeoff and landing runway identification: replaced heading+distance matching with ground track intersection against runway polygons, correctly handling parallel runways and crosswind (crabbing) scenarios
- Added `match_runway_by_track`, `match_runway_for_takeoff` and `match_runway_for_landing` utilities in `runway.py`
- Added `collect_location_events_before` and `collect_location_events_after` utilities in `location.py`
- Applied the new runway matching logic to both detectors (`TakeoffDetector`, `FinalLandingDetector`) and analyzers (`TakeoffAnalyzer`, `FinalLandingAnalyzer`)

## [1.2.0] - 2026-02-20

- Flight plan context (departure and landing airport runway data) can now be provided via `--context` and is used to improve backtrack, takeoff and landing phase detection using runway geometry (polygon intersection) instead of heading-only heuristics
- Takeoff analyzer now identifies the departure runway and computes remaining runway percentage at liftoff (`TakeoffRunway`, `TakeoffRunwayRemainingPct`)
- Landing analyzer now identifies the landing runway and computes the touchdown point as a percentage of the landing distance available (`LandingRunway`, `LandingRunwayTouchdownPct`)
- Landing analyzer now generates issues when the aircraft lands at an unplanned airport (`LandingAirportNotPlanned`), at an alternative (`LandingAirportAlternative`), or outside any known airport (`LandingOutOfAirport`)

## [1.1.0] - 2026-02-04
- Added ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL (using new attribute VSLast3Avg) which is generated below 1000AGL and less than -1150fpm
- Modified ISSUE_APP_HIGH_VS_BELOW_1000AGL now generated below 1000AGL and less than -1500fpm

## [1.0.0] - 2026-01-31

- Initial version
