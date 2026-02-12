import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root / "src"))
sys.path.insert(0, str(_root / "tests"))

import json
import math
from typing import List

from mam_analyzer.models.flight_events import FlightEvent
from mam_analyzer.phases.phases_aggregator import FlightPhase, PhasesAggregator
from runway_data import AIRPORT_RUNWAYS, make_flight_context

FLIGHT_AIRPORTS = {
    "LEPA-LEPP-737.json": ("LEPA", "LEPP"),
    "LEPP-LEMG-737.json": ("LEPP", "LEMG"),
    "LPMA-Circuits-737.json": ("LPMA", "LPMA"),
    "UHMA-PAOM-B350.json": ("UHMA", "PAOM"),
    "UHPT-UHMA-B350.json": ("UHPT", "UHMA"),
    "UHPT-UHMA-SF34.json": ("UHPT", "UHMA"),
    "UHSH-UHMM-B350.json": ("UHSH", "UHMM"),
    "PAOM-PANC-B350-fromtaxi.json": ("PAOM", "PANC"),
    "LEBB-touchgoLEXJ-LEAS.json": ("LEBB", "LEAS"),
    "ENRA_ENDU_False_refueling.json": ("ENRA", "ENDU"),
    "LEVD-fast-crash.json": ("LEVD", "LEVD"),
    "CYBL_KEUG_REFUELING.json": ("CYBL", "KEUG"),
    "backtrack_1.json": ("EFKS", "EFVA"),
    "backtrack_2.json": ("EFKT", "EFKS"),
    "backtrack_3.json": ("ENNA", "EFKI"),
    "backtrack_4.json": ("ENDU", "ENKR"),
    "backtrack_5.json": ("ESNX", "ENRA"),
    "backtrack_6.json": ("EFVA", "EETN"),
    "zfw.json": ("OOMS", "LTFM"),
    "zfw_modified.json": ("OOMS", "LTFM"),
    "short_flight_vslast3avg.json": ("LEBL", "LEBL"),
}

PHASE_COLORS = {
    "startup": "#00ccff",
    "takeoff": "#00ff00",
    "final_landing": "#ff9900",
    "touch_go": "purple",
    "shutdown": "#cc00cc",
    "taxi": "yellow",
    "backtrack": "brown",
    "none": "#888888",
    "approach": "red",
    "cruise": "blue",
}


def runway_corners_lonlat(lat1, lon1, lat2, lon2, width_m):
    """Compute runway polygon corners as [[lon, lat], ...] for OpenLayers."""
    bearing = math.atan2(
        math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2)),
        math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
        - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(lon2 - lon1)),
    )
    perp = bearing + math.pi / 2
    half_w = width_m / 2
    dlat = (half_w / 111320) * math.cos(perp)
    mid_lat = math.radians((lat1 + lat2) / 2)
    dlon = (half_w / (111320 * math.cos(mid_lat))) * math.sin(perp)
    return [
        [lon1 + dlon, lat1 + dlat],
        [lon2 + dlon, lat2 + dlat],
        [lon2 - dlon, lat2 - dlat],
        [lon1 - dlon, lat1 - dlat],
        [lon1 + dlon, lat1 + dlat],
    ]


def get_runway_polygons(filename):
    """Get runway polygons as dicts for a flight file."""
    airports = FLIGHT_AIRPORTS.get(filename)
    if not airports:
        return []
    dep_icao, arr_icao = airports
    polygons = []
    seen_airports = set()
    for icao, role in [(dep_icao, "departure"), (arr_icao, "landing")]:
        if icao in seen_airports:
            for p in polygons:
                if p["airport"] == icao:
                    p["role"] = "both"
            continue
        seen_airports.add(icao)
        for rwy in AIRPORT_RUNWAYS.get(icao, []):
            e1, e2 = rwy.ends
            corners = runway_corners_lonlat(
                e1.latitude, e1.longitude, e2.latitude, e2.longitude, rwy.width_m
            )
            polygons.append({
                "designators": rwy.designators,
                "airport": icao,
                "role": role,
                "coordinates": corners,
                "ends": [
                    {"designator": e1.designator, "position": [e1.longitude, e1.latitude]},
                    {"designator": e2.designator, "position": [e2.longitude, e2.latitude]},
                ],
            })
    return polygons


def get_flight_context(filename):
    """Get FlightContext for a flight file if airports are known."""
    airports = FLIGHT_AIRPORTS.get(filename)
    if not airports:
        return None
    return make_flight_context(airports[0], airports[1], with_runways=True)


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
        #legend {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(255,255,255,0.9);
            padding: 10px 14px;
            border-radius: 6px;
            font: 13px/1.6 sans-serif;
            z-index: 10;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        }}
        #legend h4 {{ margin: 0 0 6px; font-size: 14px; }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .legend-swatch {{
            width: 20px; height: 12px; border-radius: 2px;
            border: 1px solid rgba(0,0,0,0.3);
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/ol@v10.6.0/dist/ol.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@v10.6.0/ol.css">
</head>
<body>
    <div id="map"></div>
    <div id="legend">
        <h4>Runways</h4>
        <div class="legend-item"><span class="legend-swatch" style="background:rgba(0,200,0,0.5)"></span> Departure</div>
        <div class="legend-item"><span class="legend-swatch" style="background:rgba(255,140,0,0.5)"></span> Landing</div>
        <div class="legend-item"><span class="legend-swatch" style="background:rgba(160,0,200,0.5)"></span> Both</div>
    </div>
    <script>
        const segments = {segments_json};
        const runways = {runways_json};

        // Flight path layers
        const pathLayers = segments.map(seg => {{
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

        // Runway polygon layers
        const runwayFillColors = {{
            'departure': 'rgba(0, 200, 0, 0.35)',
            'landing':   'rgba(255, 140, 0, 0.35)',
            'both':      'rgba(160, 0, 200, 0.35)',
        }};
        const runwayStrokeColors = {{
            'departure': 'rgba(0, 200, 0, 0.8)',
            'landing':   'rgba(255, 140, 0, 0.8)',
            'both':      'rgba(160, 0, 200, 0.8)',
        }};

        const runwayLayers = runways.map(rwy => {{
            const coords = rwy.coordinates.map(c => ol.proj.fromLonLat(c));
            const polyFeature = new ol.Feature({{
                geometry: new ol.geom.Polygon([coords])
            }});
            const features = [polyFeature];
            rwy.ends.forEach(end => {{
                const f = new ol.Feature({{
                    geometry: new ol.geom.Point(ol.proj.fromLonLat(end.position))
                }});
                f.set('label', end.designator);
                features.push(f);
            }});
            const fill = runwayFillColors[rwy.role] || runwayFillColors['both'];
            const stroke = runwayStrokeColors[rwy.role] || runwayStrokeColors['both'];
            const source = new ol.source.Vector({{ features: features }});
            return new ol.layer.Vector({{
                source: source,
                style: function(feature) {{
                    if (feature.getGeometry().getType() === 'Point') {{
                        return new ol.style.Style({{
                            text: new ol.style.Text({{
                                text: feature.get('label'),
                                font: 'bold 13px sans-serif',
                                fill: new ol.style.Fill({{ color: '#fff' }}),
                                stroke: new ol.style.Stroke({{ color: '#000', width: 3 }}),
                                offsetY: -14,
                            }}),
                            image: new ol.style.Circle({{
                                radius: 4,
                                fill: new ol.style.Fill({{ color: stroke }}),
                            }})
                        }});
                    }}
                    return new ol.style.Style({{
                        fill: new ol.style.Fill({{ color: fill }}),
                        stroke: new ol.style.Stroke({{ color: stroke, width: 2 }})
                    }});
                }}
            }});
        }});

        const map = new ol.Map({{
            target: 'map',
            layers: [
                new ol.layer.Tile({{
                    source: new ol.source.OSM()
                }}),
                ...runwayLayers,
                ...pathLayers
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

    for json_file in sorted(data_dir.glob("*.json")):
        print(f"Generating: {json_file}:")
        with open(json_file, "r") as f:
            raw_json = json.load(f)

        raw_events = raw_json["Events"]
        events = [FlightEvent.from_json(e) for e in raw_events]

        ctx = get_flight_context(json_file.name)
        aggregator = PhasesAggregator()
        phases = aggregator.identify_phases(events, context=ctx)

        segments = extract_segmented_coordinates(events, phases)
        if not segments:
            print(f"[!] No segments with coordinates in {json_file.name}")
            continue

        runway_polys = get_runway_polygons(json_file.name)

        html_content = TEMPLATE_HTML.format(
            flight_name=json_file.stem,
            segments_json=json.dumps(segments),
            runways_json=json.dumps(runway_polys),
        )

        output_file = output_dir / f"{json_file.stem}.html"
        with open(output_file, "w") as f:
            f.write(html_content)

        print(f"[✓] Generated: {output_file}\n")


if __name__ == "__main__":
    main()
