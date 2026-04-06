# Changelog

## [1.6.0] - 2026-04-06

- Added two-band vertical speed monitoring below 1000 ft AGL during approach:
  - **500–1000 ft AGL** (issues `AppHighVsBelow1000AGL` / `AppHighVsAvgBelow1000AGL`): instantaneous VS limit -2000 fpm, rolling-average limit -1650 fpm (both relaxed by the existing glideslope margin when applicable)
  - **Below 500 ft AGL** (new issues `AppHighVsBelow500AGL` / `AppHighVsAvgBelow500AGL`): instantaneous VS limit -1500 fpm, rolling-average limit -1150 fpm (same thresholds previously applied below 1000 ft, relaxed by glideslope margin when applicable)
- `AppHighVsBelow1000AGL` and `AppHighVsAvgBelow1000AGL` now cover the 500–999 ft AGL band with the stricter -2000 / -1650 fpm base limits instead of the former -1500 / -1150 fpm limits

## [1.5.0] - 2026-03-24

- Extended glideslope-based threshold relaxation to `ISSUE_APP_HIGH_VS_BELOW_2000AGL`: the same margin (2.85 fpm per 0.01° above 3°) now applies to the -2000 fpm limit between 1000–2000 ft AGL
- Issue values for `ISSUE_APP_HIGH_VS_BELOW_2000AGL` now include the applied reference threshold: `{vs}|{agl}|{threshold}`

## [1.4.0] - 2026-03-22

- Added `max_glideslope_deg` field to `RunwayEnd` (loaded from `context.json`)
- Approach analyzer now adjusts the 1000 AGL vertical speed thresholds for steep-approach runways: for each 0.01° above 3°, 2.85 fpm of margin is added to both the instantaneous limit (-1500 fpm) and the rolling-average limit (-1150 fpm). With no glideslope data, the standard 3° thresholds are used unchanged
- Added `glideslope_deg` parameter to the `Analyzer.analyze()` interface (standard pattern for passing runway data to analyzers)
- Issue values for `ISSUE_APP_HIGH_VS_BELOW_1000AGL` and `ISSUE_APP_HIGH_VS_AVG_BELOW_1000AGL` now include the applied reference threshold at the end: `{vs}|{agl},{threshold}`

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
