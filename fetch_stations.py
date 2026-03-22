#!/usr/bin/env python3
"""Fetch London station data from the TfL Unified API."""

import json
from pathlib import Path

import requests

DATA_DIR = Path("data")
OUTPUT_PATH = DATA_DIR / "stations.json"

MODES = ["tube", "dlr", "overground", "elizabeth-line"]

# London bounding box for filtering national-rail
LON_BOUNDS = {"min_lat": 51.28, "max_lat": 51.70, "min_lon": -0.51, "max_lon": 0.33}


def _fetch_national_rail():
    """Fetch national rail stations using line-by-line approach (bulk endpoint times out)."""
    print("Fetching national-rail stations from TfL API (via lines)...")
    # Get all national-rail lines that TfL knows about
    resp = requests.get("https://api.tfl.gov.uk/Line/Mode/national-rail")
    resp.raise_for_status()
    lines = resp.json()

    all_points = []
    seen_ids = set()
    for line in lines:
        line_id = line["id"]
        resp = requests.get(f"https://api.tfl.gov.uk/Line/{line_id}/StopPoints")
        if resp.status_code != 200:
            continue
        points = resp.json()
        for p in points:
            if p.get("id") not in seen_ids:
                seen_ids.add(p["id"])
                # Add national-rail mode if not present
                if "modes" not in p:
                    p["modes"] = ["national-rail"]
                elif "national-rail" not in p["modes"]:
                    p["modes"].append("national-rail")
                all_points.append(p)
    print(f"  Got {len(all_points)} national-rail stop points")
    return all_points


def fetch_stations():
    """Fetch station stop points from TfL and save as GeoJSON."""
    DATA_DIR.mkdir(exist_ok=True)

    stop_points = []
    for mode in MODES:
        print(f"Fetching {mode} stations from TfL API...")
        url = f"https://api.tfl.gov.uk/StopPoint/Mode/{mode}"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        points = data.get("stopPoints", data) if isinstance(data, dict) else data
        print(f"  Got {len(points)} stop points")
        stop_points.extend(points)

    # Add national rail separately
    stop_points.extend(_fetch_national_rail())

    # Deduplicate by station name — merge modes for multi-modal stations
    stations_by_name = {}
    for sp in stop_points:
        name = sp.get("commonName", sp.get("name", "Unknown"))
        # Clean up suffixes and location qualifiers
        clean_name = (
            name.replace(" Underground Station", "")
            .replace(" Rail Station", "")
            .replace(" DLR Station", "")
            .replace(" Station", "")
            .replace(" (London)", "")
            .strip()
        )

        modes = set()
        for m in sp.get("modes", []):
            if m in ("tube", "dlr", "overground", "elizabeth-line", "national-rail"):
                modes.add(m)
        if not modes:
            continue

        lat = sp.get("lat")
        lon = sp.get("lon")
        if lat is None or lon is None:
            continue

        # Filter to London area
        if not (LON_BOUNDS["min_lat"] <= lat <= LON_BOUNDS["max_lat"]
                and LON_BOUNDS["min_lon"] <= lon <= LON_BOUNDS["max_lon"]):
            continue

        if clean_name in stations_by_name:
            stations_by_name[clean_name]["modes"].update(modes)
        else:
            stations_by_name[clean_name] = {
                "name": clean_name,
                "lat": lat,
                "lon": lon,
                "modes": modes,
            }

    # Convert to GeoJSON
    features = []
    for station in sorted(stations_by_name.values(), key=lambda s: s["name"]):
        modes_list = sorted(station["modes"])
        # Primary mode determines the icon (priority: tube > elizabeth-line > dlr > overground > national-rail)
        priority = ["tube", "elizabeth-line", "dlr", "overground", "national-rail"]
        primary = next((m for m in priority if m in modes_list), modes_list[0])

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [station["lon"], station["lat"]],
                },
                "properties": {
                    "name": station["name"],
                    "modes": modes_list,
                    "primary_mode": primary,
                },
            }
        )

    geojson = {"type": "FeatureCollection", "features": features}

    OUTPUT_PATH.write_text(json.dumps(geojson, indent=2))
    print(f"Saved {len(features)} stations to {OUTPUT_PATH}")

    # Summary by mode
    mode_counts = {}
    for f in features:
        for m in f["properties"]["modes"]:
            mode_counts[m] = mode_counts.get(m, 0) + 1
    for mode, count in sorted(mode_counts.items()):
        print(f"  {mode}: {count}")

    return geojson


if __name__ == "__main__":
    fetch_stations()
