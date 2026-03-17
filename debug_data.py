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
    print("OFSTED DATA")
    print("=" * 60)

    try:
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="cp1252", low_memory=False)

    print(f"Total rows: {len(df)}")
    print(f"\nAll columns ({len(df.columns)}):")
    for col in df.columns:
        print(f"  - {col}")

    # Check URN column
    urn_col = None
    for c in ["URN", "urn", "Urn"]:
        if c in df.columns:
            urn_col = c
            break
    if urn_col:
        print(f"\nURN column '{urn_col}' dtype: {df[urn_col].dtype}")
        print(f"URN sample: {df[urn_col].head(3).tolist()}")
    else:
        print("\nNo URN column found!")

    # Check for rating columns
    rating_cols = [c for c in df.columns if "overall" in c.lower() or "effectiveness" in c.lower() or "rating" in c.lower()]
    if rating_cols:
        print(f"\nRating-related columns: {rating_cols}")
        for col in rating_cols:
            vals = df[col].dropna()
            print(f"\n  '{col}':")
            print(f"    dtype: {vals.dtype}")
            print(f"    non-null count: {len(vals)}")
            print(f"    unique values: {vals.unique()[:15]}")
            print(f"    value counts:\n{vals.value_counts().head(10).to_string()}")
    else:
        print("\nNo rating-related columns found!")

    # Show first row as example
    print(f"\nFirst row sample:")
    print(df.iloc[0].to_string())


if __name__ == "__main__":
    inspect_gias()
    inspect_ofsted()
