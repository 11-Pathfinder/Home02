#!/usr/bin/env python3
"""London Primary Schools Catchment Area Mapper.

Downloads school data from GIAS and Ofsted, filters to London primary schools,
and generates an interactive HTML map with color-coded catchment areas.

Usage:
    python3 main.py                  # Run full pipeline
    python3 main.py --refresh        # Force re-download of data
    python3 main.py --refresh-legacy # Re-fetch legacy ratings from Ofsted website
    python3 main.py --radius 1000    # Custom catchment radius (meters)
    python3 main.py --output map.html  # Custom output file
    python3 main.py --check "Joseph Hood"  # Check a school's rating
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
        "--refresh-legacy",
        action="store_true",
        help="Re-fetch legacy ratings from Ofsted website",
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
    parser.add_argument(
        "--check",
        type=str,
        default=None,
        help="Check a school's rating by name (partial, case-insensitive match)",
    )
    parser.add_argument(
        "--ofsted-url",
        type=str,
        default=None,
        help="Manually specify the Ofsted CSV download URL",
    )
    args = parser.parse_args()

    # Step 1: Download data
    print("=" * 60)
    print("Step 1: Fetching data...")
    print("=" * 60)
    gias_path, ofsted_path = fetch_all(force=args.refresh, ofsted_url=args.ofsted_url)

    # Step 2: Process data
    print("\n" + "=" * 60)
    print("Step 2: Processing data...")
    print("=" * 60)
    schools_df = process(gias_path, ofsted_path, refresh_legacy=args.refresh_legacy)

    # Step 3: Generate map
    print("\n" + "=" * 60)
    print("Step 3: Generating map...")
    print("=" * 60)
    output_path = generate_map(
        schools_df,
        radius_m=args.radius,
        output_path=args.output,
    )

    # Check a specific school if requested
    if args.check:
        print("\n" + "=" * 60)
        print(f"Checking schools matching: '{args.check}'")
        print("=" * 60)
        mask = schools_df["Name"].str.contains(args.check, case=False, na=False)
        matches = schools_df[mask]
        if matches.empty:
            print(f"  No schools found matching '{args.check}'")
        else:
            for _, row in matches.iterrows():
                print(f"  URN: {row['URN']}")
                print(f"  Name: {row['Name']}")
                print(f"  Borough: {row['Borough']}")
                print(f"  Ofsted: {row['OfstedRating']}")
                print(f"  Address: {row.get('Address', 'N/A')}")
                print()
        # Also check raw Ofsted data
        if ofsted_path and Path(ofsted_path).exists():
            import pandas as pd
            from process_data import load_ofsted_data
            raw_ofsted, _ = load_ofsted_data(ofsted_path)
            if raw_ofsted is not None:
                for _, row in matches.iterrows():
                    urn = int(row["URN"])
                    in_ofsted = raw_ofsted[raw_ofsted["URN"] == urn]
                    if in_ofsted.empty:
                        print(f"  !! URN {urn} ({row['Name']}) NOT found in Ofsted CSV")
                    else:
                        print(f"  >> URN {urn} in Ofsted CSV with rating: {in_ofsted.iloc[0]['OfstedRating']}")

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
