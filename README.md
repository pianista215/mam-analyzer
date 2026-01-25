# MAM Analyzer

Flight data analyzer for the MAM (Modern Airlines Manager) ecosystem. Reads black box data recorded by [MAM ACARS](https://github.com/pianista215/mam-acars) and generates analysis reports that are processed and visualized by [MAM](https://github.com/pianista215/mam).

## Related Projects

- [MAM](https://github.com/pianista215/mam) - Main web application for airline management
- [MAM ACARS](https://github.com/pianista215/mam-acars) - Flight recorder that captures black box data

## What it does

- Parses flight event JSON files from MAM ACARS
- Detects flight phases: startup, taxi, backtrack, takeoff, cruise, approach, touch-and-go, landing, shutdown
- Calculates flight metrics: block time, airborne time, fuel consumed, distance
- Detects issues: hard landings, taxi overspeed, high descent rates, engine failures, refueling

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Installation

Install uv (if not already installed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Clone and install dependencies:

```bash
git clone https://github.com/pianista215/mam-analyzer.git
cd mam-analyzer
uv sync --all-extras
```

## Usage

### Analyze a flight file

```bash
uv run python scripts/run.py <input.json> <output.json>
```

Example:

```bash
uv run python scripts/run.py data/LEVD-fast-crash.json /tmp/analysis.json
```

### Run tests

```bash
# All tests
uv run pytest

# Single test file
uv run pytest tests/phases/detectors/test_phases_takeoff.py

# Tests matching a pattern
uv run pytest -k "takeoff"

# With verbose output
uv run pytest -v
```

### Using the activated environment

If you prefer working with an activated virtual environment:

```bash
source .venv/bin/activate

# Now you can run commands directly
pytest
python scripts/run.py data/LEVD-fast-crash.json /tmp/analysis.json
```

## Managing dependencies

```bash
# Add a runtime dependency
uv add requests

# Add a dev dependency
uv add --dev black

# Update all dependencies
uv sync --upgrade
```

## Output

The analyzer produces a JSON report with:

- **global**: Flight-wide metrics (block time, airborne time, fuel consumed, distance)
- **phases**: List of detected phases with their own metrics and issues

### Issues detected

| Code | Description |
|------|-------------|
| `LandingHardFpm` | Hard landing (high vertical speed at touchdown) |
| `TaxiOverspeed` | Exceeded taxi speed limit |
| `AppHighVsBelow1000AGL` | High vertical speed below 1000ft AGL on approach |
| `AppHighVsBelow2000AGL` | High vertical speed below 2000ft AGL on approach |
| `Refueling` | Mid-flight refueling detected |
| `AirborneEngineStopped` | Single engine failure in flight |
| `AirborneAllEnginesStopped` | All engines stopped in flight |
| `LandingSomeEngineStopped` | Landing with engine(s) stopped |
| `LandingAllEnginesStopped` | Landing with all engines stopped |
| `ZfwModified` | Zero fuel weight changed during flight |

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This means:
- You can use, modify, and distribute this software
- Any derivative work must also be licensed under AGPL-3.0
- If you run a modified version as a network service, you must make the source code available to users
- See [LICENSE](LICENSE) for the full text

Copyright (c) 2026 Unai Sarasola Álvarez
