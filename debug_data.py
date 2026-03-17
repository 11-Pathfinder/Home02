#!/usr/bin/env python3
"""Diagnostic script to inspect downloaded data files and debug rating merge."""

import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")


def inspect_gias():
    path = DATA_DIR / "edubasealldata.csv"
    if not path.exists():
        print("GIAS file not found")
        return

    print("=" * 60)
    print("GIAS DATA")
    print("=" * 60)

    try:
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="cp1252", low_memory=False)

    print(f"Total rows: {len(df)}")
    print(f"\nAll columns ({len(df.columns)}):")
    for col in df.columns:
        print(f"  - {col}")

    # Check for any Ofsted-related columns
    ofsted_cols = [c for c in df.columns if "ofsted" in c.lower() or "rating" in c.lower() or "effectiveness" in c.lower()]
    if ofsted_cols:
        print(f"\nOfsted-related columns found: {ofsted_cols}")
        for col in ofsted_cols:
            print(f"  {col} unique values: {df[col].dropna().unique()[:10]}")
    else:
        print("\nNo Ofsted-related columns found in GIAS data")

    # Check URN column
    print(f"\nURN column dtype: {df['URN'].dtype}")
    print(f"URN sample: {df['URN'].head(3).tolist()}")


def inspect_ofsted():
    path = DATA_DIR / "ofsted_inspections.csv"
    if not path.exists():
        print("\nOfsted file not found")
        return

    print("\n" + "=" * 60)
    print("OFSTED DATA - RAW FILE SCAN")
    print("=" * 60)

    # Read raw lines to find where the actual headers are
    for enc in ["utf-8-sig", "cp1252", "latin-1"]:
        try:
            with open(path, encoding=enc) as f:
                lines = [f.readline() for _ in range(30)]
            break
        except UnicodeDecodeError:
            continue

    # Line 2 has the headers. Parse with skiprows=2
    for enc in ["utf-8-sig", "cp1252", "latin-1"]:
        try:
            df = pd.read_csv(path, encoding=enc, skiprows=2, low_memory=False)
            break
        except UnicodeDecodeError:
            continue

    print(f"Total rows: {len(df)}")
    print(f"\nAll columns ({len(df.columns)}):")
    for col in df.columns:
        print(f"  - {col}")

    # Show rating-related columns
    rating_cols = [c for c in df.columns if "overall" in c.lower() or "effectiveness" in c.lower()]
    if rating_cols:
        print(f"\nRating columns found: {rating_cols}")
        for col in rating_cols:
            vals = df[col].dropna()
            print(f"\n  '{col}' — {len(vals)} non-null values")
            print(f"  Value counts:\n{vals.value_counts().to_string()}")
    else:
        print("\nNo 'overall effectiveness' column found!")

    print(f"\nURN dtype: {df['URN'].dtype}")
    print(f"URN sample: {df['URN'].head(3).tolist()}")
    print(f"\nSample row:")
    print(df.iloc[0].to_string())


if __name__ == "__main__":
    inspect_gias()
    inspect_ofsted()
