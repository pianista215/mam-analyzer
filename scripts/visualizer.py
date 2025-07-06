import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.phases_aggregator import FlightPhase, PhasesAggregator

PHASE_COLORS = {
    "startup": "#00ccff",
    "takeoff": "#00ff00",
    "final_landing": "#ff9900",
    "touch_go": "purple",
    "shutdown": "#cc00cc",
    "taxi": "yellow",
    "none": "#888888",
    "approach": "red",
    "cruise": "blue",
}

TEMPLATE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Flight Visualization - {flight_name}</title>
    <meta charset="utf-8">
    <style>
        html, body, #map {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/ol@v10.6.0/dist/ol.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@v10.6.0/ol.css">
</head>
<body>
    <div id="map"></div>
    <script>
        const segments = {segments_json};

        const layers = segments.map(seg => {{
            const coords = seg.coordinates.map(c => ol.proj.fromLonLat(c));
            const feature = new ol.Feature({{
                geometry: new ol.geom.LineString(coords)
            }});
            const source = new ol.source.Vector({{ features: [feature] }});
            return new ol.layer.Vector({{
                source: source,
                style: new ol.style.Style({{
                    stroke: new ol.style.Stroke({{
                        color: seg.color,
                        width: 3
                    }})
                }})
            }});
        }});

        const map = new ol.Map({{
            target: 'map',
            layers: [
                new ol.layer.Tile({{
                    source: new ol.source.OSM()
                }}),
                ...layers
            ],
            view: new ol.View({{
                center: ol.proj.fromLonLat(segments[Math.floor(segments.length / 2)].coordinates[0]),
                zoom: 10
            }})
        }});
    </script>
</body>
</html>
"""


def assign_phase(phases: List[FlightPhase], event: FlightEvent) -> str:
    for phase in phases:
        if phase.contains(event):
            return phase.name
    return "none"

def extract_segmented_coordinates(events: List[FlightEvent], phases: List[FlightPhase]) -> List[dict]:
    segments = []
    last_phase = None
    current_segment = []

    for e in events:
        lat = e.latitude
        lon = e.longitude
        if lat is None or lon is None:
            continue

        phase = assign_phase(phases, e)

        if phase != last_phase and current_segment:
            # Save previous segment connected to this new position
            current_segment.append([float(lon), float(lat)])
            segments.append({
                "phase": last_phase,
                "color": PHASE_COLORS.get(last_phase, PHASE_COLORS["none"]),
                "coordinates": current_segment
            })
            current_segment = []

        current_segment.append([float(lon), float(lat)])
        last_phase = phase

    if current_segment:
        segments.append({
            "phase": last_phase,
            "color": PHASE_COLORS.get(last_phase, PHASE_COLORS["none"]),
            "coordinates": current_segment
        })

    return segments

def main():
    data_dir = Path("data")
    output_dir = Path("/tmp")
    output_dir.mkdir(parents=True, exist_ok=True)

    for json_file in data_dir.glob("*.json"):
        print(f"Generating: {json_file}:")
        with open(json_file, "r") as f:
            raw_json = json.load(f)

        raw_events = raw_json["Events"]
        events = [FlightEvent.from_json(e) for e in raw_events]

        aggregator = PhasesAggregator()
        phases = aggregator.identify_phases(events)

        segments = extract_segmented_coordinates(events, phases)
        if not segments:
            print(f"[!] No segments with coordinates in {json_file.name}")
            continue

        html_content = TEMPLATE_HTML.format(
            flight_name=json_file.stem,
            segments_json=json.dumps(segments)
        )

        output_file = output_dir / f"{json_file.stem}.html"
        with open(output_file, "w") as f:
            f.write(html_content)

        print(f"[✓] Generated: {output_file}\n")

if __name__ == "__main__":
    main()
