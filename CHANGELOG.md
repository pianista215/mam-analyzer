# Changelog

## [1.8.0] - 2026-05-27

### Backtrack detector rewrite

- **Segment-based corridor matching**: the detector now tests line segments between consecutive GPS points against the runway safe zone instead of individual GPS points. This fixes cases where sparse GPS sampling caused all points to fall just outside the runway polygon even though the aircraft was clearly on the runway
- **Direction filtering**: only segments whose movement vector is within 30° of the backtrack direction (opposite to the takeoff/landing run vector) are counted as backtrack candidates. This eliminates false positives from perpendicular runway crossings
- **Last-significant-segment logic**: instead of stopping at the first exit from the safe zone, the detector collects all qualifying runs, filters them by a minimum length threshold, and returns the *last* qualifying run. This makes detection robust against brief GPS excursions outside the corridor and prevents early runway crossings from masking the real backtrack
- **`takeoff_vector` / `landing_vector` now actively used**: both vectors were previously computed but unused; they now drive the backtrack direction check
- **`_vector_magnitude` helper**: extracted the repeated `sqrt(x² + y²)` pattern into a reusable private method used across `extend_line`, `angle_between_vectors` and `_find_last_qualifying_segment`
- **New integration tests** (`tests/phases/detectors/test_phases_backtrack.py`): isolated detector tests for `detect_from_takeoff` and `detect_from_landing` covering positive and negative cases for backtrack files 1–13, with and without runway context, independent of other detectors
- **New airport runway data** added to `tests/runway_data.py`: LEVX, CYZF, CYHY, CYDL, PAWG, LEGE, CYQH

## [1.7.0] - 2026-05-23

- Taxi overspeed check now exempts the last ~100 m before runway entry (pre-takeoff taxi) and the first ~100 m after runway exit (post-landing taxi), to avoid false positives when the aircraft is entering or leaving the runway
- Exemption is computed from GPS coordinates using cumulative haversine distance; falls back to no exemption if location data is unavailable
- Taxi overspeed check now also exempts any event whose position falls inside a runway polygon of the relevant airport (departure for pre-takeoff, landing/destination for post-landing), suppressing false positives when taxiing across or along a runway (including parallel runways) or when the backtrack detector misfires
- Added `build_all_runway_polygons` and `point_on_any_runway` utilities to `utils/runway.py`

## [1.6.1] - 2026-04-27

- Fixed crash when a touch-and-go approach window is less than 30 seconds (caused by consecutive touch-and-goes with no time between them): the approach phase is now silently skipped in that case

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
