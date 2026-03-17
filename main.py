#!/usr/bin/env python3
"""London Primary Schools Catchment Area Mapper.

Downloads school data from GIAS and Ofsted, filters to London primary schools,
and generates an interactive HTML map with color-coded catchment areas.

Usage:
    python3 main.py                  # Run full pipeline
    python3 main.py --refresh        # Force re-download of data
    python3 main.py --radius 1000    # Custom catchment radius (meters)
    python3 main.py --output map.html  # Custom output file
"""

import argparse
from pathlib import Path

from config import DEFAULT_CATCHMENT_RADIUS_M
from fetch_data import fetch_all
from generate_map import generate_map
from process_data import process


def main():
    parser = argparse.ArgumentParser(
        description="Generate a map of London primary schools with catchment areas"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-download of all data",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=DEFAULT_CATCHMENT_RADIUS_M,
        help=f"Catchment circle radius in meters (default: {DEFAULT_CATCHMENT_RADIUS_M})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output HTML file path (default: output/london_schools_map.html)",
    )
    args = parser.parse_args()

    # Step 1: Download data
    print("=" * 60)
    print("Step 1: Fetching data...")
    print("=" * 60)
    gias_path, ofsted_path = fetch_all(force=args.refresh)

    # Step 2: Process data
    print("\n" + "=" * 60)
    print("Step 2: Processing data...")
    print("=" * 60)
    schools_df = process(gias_path, ofsted_path)

    # Step 3: Generate map
    print("\n" + "=" * 60)
    print("Step 3: Generating map...")
    print("=" * 60)
    output_path = generate_map(
        schools_df,
        radius_m=args.radius,
        output_path=args.output,
    )

    # Summary
    print("\n" + "=" * 60)
    print("Done!")
    print(f"  Schools mapped: {len(schools_df)}")
    print(f"  Catchment radius: {args.radius}m")
    print(f"  Map file: {output_path}")
    print("  Open the HTML file in a browser to view the map.")
    print("=" * 60)


if __name__ == "__main__":
    main()
