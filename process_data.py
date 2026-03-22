"""Process and filter school data for London primary schools."""

from pathlib import Path

import pandas as pd
from pyproj import Transformer

from config import LONDON_BOROUGHS
from fetch_data import fetch_legacy_ratings

DATA_DIR = Path("data")

# British National Grid (EPSG:27700) to WGS84 (EPSG:4326) transformer
_transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def _bng_to_latlng(easting, northing):
    """Convert British National Grid coordinates to latitude/longitude."""
    lng, lat = _transformer.transform(easting, northing)
    return lat, lng


def load_gias_data(gias_path):
    """Load and filter GIAS data to London primary schools."""
    print("Loading GIAS data...")
    # GIAS CSV uses Windows-1252 encoding (contains curly quotes etc.)
    try:
        df = pd.read_csv(gias_path, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(gias_path, encoding="cp1252", low_memory=False)
    print(f"  Total establishments: {len(df)}")

    # Identify relevant columns (GIAS uses varying naming conventions)
    # Try to find the phase column
    phase_col = None
    for candidate in ["PhaseOfEducation (name)", "PhaseOfEducation", "Phase"]:
        if candidate in df.columns:
            phase_col = candidate
            break

    status_col = None
    for candidate in ["EstablishmentStatus (name)", "EstablishmentStatus", "Status"]:
        if candidate in df.columns:
            status_col = candidate
            break

    la_col = None
    for candidate in ["LA (name)", "LA"]:
        if candidate in df.columns:
            la_col = candidate
            break

    name_col = None
    for candidate in ["EstablishmentName", "Name"]:
        if candidate in df.columns:
            name_col = candidate
            break

    if not all([phase_col, status_col, la_col, name_col]):
        print("Warning: Could not identify all required columns.")
        print(f"  Available columns: {list(df.columns[:30])}")
        missing = []
        if not phase_col:
            missing.append("Phase")
        if not status_col:
            missing.append("Status")
        if not la_col:
            missing.append("LA")
        if not name_col:
            missing.append("Name")
        raise ValueError(f"Missing columns: {missing}")

    # Filter to open primary schools
    open_mask = df[status_col].str.contains("Open", case=False, na=False)
    primary_mask = df[phase_col].str.contains("Primary", case=False, na=False)
    df_state = df[primary_mask & open_mask].copy()
    df_state["IsPrivate"] = False
    print(f"  Open primary schools: {len(df_state)}")

    # Also include independent (private) primary-age schools
    type_group_col = None
    for candidate in ["EstablishmentTypeGroup (name)", "EstablishmentTypeGroup"]:
        if candidate in df.columns:
            type_group_col = candidate
            break
    df_private = pd.DataFrame()
    if type_group_col and "StatutoryLowAge" in df.columns and "StatutoryHighAge" in df.columns:
        ind_mask = (
            open_mask
            & (df[type_group_col] == "Independent schools")
            & (df["StatutoryLowAge"] <= 5)
            & (df["StatutoryHighAge"] >= 7)
        )
        df_private = df[ind_mask].copy()
        df_private["IsPrivate"] = True
        print(f"  Independent primary-age schools: {len(df_private)}")

    df = pd.concat([df_state, df_private], ignore_index=True)

    # Filter to London boroughs
    london_mask = df[la_col].isin(LONDON_BOROUGHS)
    df = df[london_mask].copy()
    print(f"  London primary schools (incl. private): {len(df)}")

    # Identify religious schools
    religious_col = None
    for candidate in ["ReligiousCharacter (name)", "ReligiousCharacter"]:
        if candidate in df.columns:
            religious_col = candidate
            break
    if religious_col:
        df["IsReligious"] = df[religious_col].notna() & (df[religious_col] != "Does not apply")
    else:
        df["IsReligious"] = False

    # Get coordinates — prefer lat/lng if available, otherwise convert from BNG
    if "Latitude" in df.columns and "Longitude" in df.columns:
        # Direct lat/lng available — some GIAS downloads include these
        pass
    elif "Easting" in df.columns and "Northing" in df.columns:
        print("  Converting Easting/Northing to lat/lng...")
        valid_coords = df["Easting"].notna() & df["Northing"].notna()
        coords = df.loc[valid_coords].apply(
            lambda row: _bng_to_latlng(row["Easting"], row["Northing"]),
            axis=1,
        )
        df.loc[valid_coords, "Latitude"] = coords.apply(lambda x: x[0])
        df.loc[valid_coords, "Longitude"] = coords.apply(lambda x: x[1])
    else:
        raise ValueError("No coordinate columns found (need Latitude/Longitude or Easting/Northing)")

    # Drop rows without coordinates
    df = df.dropna(subset=["Latitude", "Longitude"])
    print(f"  With valid coordinates: {len(df)}")

    # Check if GIAS still has Ofsted rating (unlikely post-Jan 2025)
    ofsted_col = None
    for candidate in ["OfstedRating (name)", "OfstedRating", "Ofsted Rating"]:
        if candidate in df.columns:
            ofsted_col = candidate
            break

    # Standardize column names for output
    result = pd.DataFrame({
        "URN": pd.to_numeric(df["URN"], errors="coerce").astype("Int64"),
        "Name": df[name_col],
        "Latitude": df["Latitude"],
        "Longitude": df["Longitude"],
        "Borough": df[la_col],
        "IsPrivate": df["IsPrivate"],
        "IsReligious": df["IsReligious"],
    })

    # Add address if available
    address_parts = []
    for col in ["Street", "Locality", "Town", "Postcode"]:
        if col in df.columns:
            address_parts.append(col)
    if address_parts:
        result["Address"] = df[address_parts].fillna("").agg(", ".join, axis=1)
        result["Address"] = result["Address"].str.replace(r",\s*,", ",", regex=True).str.strip(", ")
    else:
        result["Address"] = ""

    # Add Ofsted rating from GIAS if available
    if ofsted_col:
        result["OfstedRating"] = df[ofsted_col]
    else:
        result["OfstedRating"] = None

    return result


def load_ofsted_data(ofsted_path):
    """Load Ofsted inspection outcomes data.

    Returns:
        Tuple of (ratings_df, legacy_urns) where:
        - ratings_df: DataFrame with URN and OfstedRating columns
        - legacy_urns: List of URNs that have "Standards maintained" but no
          OEIF rating (need legacy lookup from Ofsted website)
    """
    if ofsted_path is None or not Path(ofsted_path).exists():
        print("No Ofsted data file available.")
        return None, []

    print("Loading Ofsted inspection data...")

    # Auto-detect the header row by finding the row containing "URN" as a cell.
    # The Ofsted MI CSV may have 0-2 metadata rows before the actual headers.
    # Use word boundary \bURN\b to avoid matching substrings like "turn".
    df = None
    for enc in ["utf-8-sig", "cp1252", "latin-1"]:
        try:
            raw = pd.read_csv(ofsted_path, encoding=enc, nrows=10, header=None)
            skip = 0
            for i, row in raw.iterrows():
                if row.astype(str).str.strip().str.upper().eq("URN").any():
                    skip = i
                    break
            df = pd.read_csv(ofsted_path, encoding=enc, skiprows=skip, low_memory=False)
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        return None, []
    print(f"  Total inspection records: {len(df)}")

    # The Ofsted MI CSV has varying column names. Try to find URN and rating.
    urn_col = None
    for candidate in ["URN", "urn", "Urn"]:
        if candidate in df.columns:
            urn_col = candidate
            break

    rating_col = None
    for candidate in [
        "Latest OEIF overall effectiveness",
        "Overall effectiveness",
        "OverallEffectiveness",
        "Overall Effectiveness",
    ]:
        if candidate in df.columns:
            rating_col = candidate
            break

    if not urn_col or not rating_col:
        print(f"  Warning: Could not find URN or rating columns.")
        print(f"  Available columns: {list(df.columns)}")
        return None, []

    print(f"  URN column: '{urn_col}', Rating column: '{rating_col}'")
    print(f"  Sample rating values: {df[rating_col].dropna().unique()[:10]}")

    # Look for the "Ungraded inspection overall outcome" column — this contains
    # Section 8 results like "School remains Good" for schools that haven't had
    # a full graded (Section 5) inspection under the OEIF framework.
    ungraded_col = None
    for candidate in [
        "Ungraded inspection overall outcome",
        "Ungraded inspection outcome",
    ]:
        if candidate in df.columns:
            ungraded_col = candidate
            break
    if ungraded_col:
        print(f"  Ungraded outcome column: '{ungraded_col}'")

    # Map numeric ratings to text; if already text, normalize them
    rating_map = {
        1: "Outstanding",
        "1": "Outstanding",
        1.0: "Outstanding",
        2: "Good",
        "2": "Good",
        2.0: "Good",
        3: "Requires improvement",
        "3": "Requires improvement",
        3.0: "Requires improvement",
        4: "Inadequate",
        "4": "Inadequate",
        4.0: "Inadequate",
        # Handle text values too (already correct labels)
        "Outstanding": "Outstanding",
        "Good": "Good",
        "Requires improvement": "Requires improvement",
        "Inadequate": "Inadequate",
    }

    result = pd.DataFrame({
        "URN": pd.to_numeric(df[urn_col], errors="coerce"),
        "OfstedRating": df[rating_col].map(rating_map),
    })

    # Infer ratings for transition period schools (Sep 2024 - Nov 2025)
    # These have "Not judged" overall effectiveness but valid sub-judgements
    sub_cols = [
        "Latest OEIF quality of education",
        "Latest OEIF behaviour and attitudes",
        "Latest OEIF personal development",
        "Latest OEIF effectiveness of leadership and management",
    ]
    available_sub_cols = [c for c in sub_cols if c in df.columns]

    if available_sub_cols:
        # Schools with no overall rating but have sub-judgements
        no_overall = result["OfstedRating"].isna()
        has_subs = df[available_sub_cols[0]].notna()

        transition_mask = no_overall & has_subs
        if transition_mask.any():
            # Infer rating from worst sub-judgement (highest number = worst grade)
            def infer_from_subs(row):
                grades = []
                for col in available_sub_cols:
                    val = row[col]
                    if pd.notna(val):
                        try:
                            grades.append(int(float(val)))
                        except (ValueError, TypeError):
                            pass
                if not grades:
                    return None
                worst = max(grades)  # Higher number = worse rating
                return rating_map.get(worst)

            inferred = df.loc[transition_mask].apply(infer_from_subs, axis=1)
            filled_count = inferred.notna().sum()
            result.loc[transition_mask, "OfstedRating"] = inferred.values
            if filled_count > 0:
                print(f"  Inferred {filled_count} ratings from sub-judgements (transition period)")

    # Identify schools that need legacy rating lookup:
    # - Have "Standards maintained" (or similar) ungraded outcome
    # - But no OEIF graded rating
    legacy_urns = []
    if ungraded_col is not None:
        # Outcomes that indicate a maintained rating (need to look up what it was)
        maintained_outcomes = [
            "Standards maintained",
            "Improved significantly",  # Still need to know what grade they improved to
            "Some aspects not as strong",  # Still maintaining previous grade
        ]
        has_maintained = df[ungraded_col].str.strip().isin(maintained_outcomes)
        no_oeif_rating = result["OfstedRating"].isna()
        needs_legacy = has_maintained & no_oeif_rating
        legacy_urns = df.loc[needs_legacy, urn_col].dropna().astype(int).tolist()
        if legacy_urns:
            print(f"  Found {len(legacy_urns)} schools needing legacy rating lookup")

    # Fill missing ratings from the ungraded outcome column (covers schools
    # whose last inspection was a Section 8 that confirmed their existing grade,
    # e.g. "School remains Good", "School remains Outstanding")
    if ungraded_col is not None:
        ungraded_map = {
            "School remains Good": "Good",
            "School remains Good (Concerns) - S5 Next": "Good",
            "School remains Good (Improving) - S5 Next": "Good",
            "School remains Outstanding": "Outstanding",
            "School remains Outstanding (Concerns) - S5 Next": "Outstanding",
        }
        fallback_ratings = df[ungraded_col].str.strip().map(ungraded_map)
        missing = result["OfstedRating"].isna()
        filled = missing.sum() - fallback_ratings[missing].isna().sum()
        result.loc[missing, "OfstedRating"] = fallback_ratings[missing]
        print(f"  Filled {int(filled)} ratings from ungraded inspection outcomes")

    # Keep only the latest inspection per school (highest index = most recent)
    result = result.dropna(subset=["OfstedRating", "URN"])
    result["URN"] = result["URN"].astype(int)
    result = result.drop_duplicates(subset=["URN"], keep="last")
    print(f"  Schools with ratings: {len(result)}")

    return result, legacy_urns


def merge_data(schools_df, ofsted_df, legacy_df=None):
    """Merge school data with Ofsted ratings.

    Args:
        schools_df: DataFrame with school data from GIAS.
        ofsted_df: DataFrame with ratings from Ofsted MI CSV.
        legacy_df: Optional DataFrame with legacy ratings fetched from Ofsted website.
    """
    if ofsted_df is None:
        # No Ofsted data — mark all as "Not yet inspected"
        schools_df["OfstedRating"] = schools_df["OfstedRating"].fillna("Not yet inspected")
        return schools_df

    # Treat "Not yet inspected" from GIAS as missing — Ofsted MI may have a real rating
    schools_df["OfstedRating"] = schools_df["OfstedRating"].replace("Not yet inspected", pd.NA)

    # Ensure URN types match for merge
    schools_df["URN"] = pd.to_numeric(schools_df["URN"], errors="coerce").astype("Int64")
    ofsted_df["URN"] = pd.to_numeric(ofsted_df["URN"], errors="coerce").astype("Int64")

    # Check overlap
    overlap = schools_df["URN"].isin(ofsted_df["URN"]).sum()
    print(f"  URN overlap: {overlap} of {len(schools_df)} schools found in Ofsted data")

    # If GIAS already has ratings, prefer those; fill gaps from Ofsted MI
    if schools_df["OfstedRating"].notna().any():
        # Merge Ofsted data only for schools missing ratings
        missing_mask = schools_df["OfstedRating"].isna()
        if missing_mask.any():
            merged = schools_df[missing_mask].drop(columns=["OfstedRating"]).merge(
                ofsted_df[["URN", "OfstedRating"]], on="URN", how="left"
            )
            schools_df.loc[missing_mask, "OfstedRating"] = merged["OfstedRating"].values
    else:
        # No GIAS ratings at all — merge entirely from Ofsted MI
        schools_df = schools_df.drop(columns=["OfstedRating"]).merge(
            ofsted_df[["URN", "OfstedRating"]], on="URN", how="left"
        )

    # Fill remaining gaps from legacy ratings (fetched from Ofsted website)
    if legacy_df is not None and len(legacy_df) > 0:
        legacy_df["URN"] = pd.to_numeric(legacy_df["URN"], errors="coerce").astype("Int64")
        missing_mask = schools_df["OfstedRating"].isna()
        if missing_mask.any():
            merged = schools_df[missing_mask].drop(columns=["OfstedRating"]).merge(
                legacy_df[["URN", "OfstedRating"]], on="URN", how="left"
            )
            filled = merged["OfstedRating"].notna().sum()
            schools_df.loc[missing_mask, "OfstedRating"] = merged["OfstedRating"].values
            if filled > 0:
                print(f"  Filled {filled} ratings from legacy Ofsted data")

    # Label private schools without Ofsted rating distinctly
    private_missing = schools_df["OfstedRating"].isna() & (schools_df["IsPrivate"] == True)
    schools_df.loc[private_missing, "OfstedRating"] = "Independent"
    not_inspected_count = schools_df["OfstedRating"].isna().sum()
    schools_df["OfstedRating"] = schools_df["OfstedRating"].fillna("Not yet inspected")
    if not_inspected_count > 0:
        print(f"  {not_inspected_count} schools have no Ofsted rating after merge")
    return schools_df


def process(gias_path, ofsted_path, refresh_legacy=False):
    """Full processing pipeline: load, filter, merge, save.

    Args:
        gias_path: Path to GIAS CSV file.
        ofsted_path: Path to Ofsted MI CSV file.
        refresh_legacy: If True, re-fetch all legacy ratings from Ofsted website.
    """
    schools = load_gias_data(gias_path)
    ofsted, legacy_urns = load_ofsted_data(ofsted_path)

    # Fetch legacy ratings for schools that need them
    # (schools with "Standards maintained" but no OEIF graded rating)
    legacy_df = None
    new_framework_urns = set()
    if legacy_urns:
        # Filter to only URNs that are actually in our London schools list
        london_urns = set(schools["URN"].dropna().astype(int).tolist())
        relevant_legacy_urns = [u for u in legacy_urns if u in london_urns]
        if relevant_legacy_urns:
            print(f"Fetching legacy ratings for {len(relevant_legacy_urns)} London schools...")
            legacy_df = fetch_legacy_ratings(relevant_legacy_urns, force=refresh_legacy)

            # Schools that needed legacy lookup but weren't found are on the new framework
            # (inspected under 2025 report card system - no traditional grades)
            if legacy_df is not None:
                fetched_urns = set(legacy_df["URN"].astype(int).tolist())
                new_framework_urns = set(u for u in relevant_legacy_urns if u not in fetched_urns)
                if new_framework_urns:
                    print(f"  {len(new_framework_urns)} schools on new 2025 report card framework")

    schools = merge_data(schools, ofsted, legacy_df)

    # Mark schools on new framework (have "Standards maintained" but no traditional grade)
    if new_framework_urns:
        mask = schools["URN"].isin(new_framework_urns)
        schools.loc[mask, "OfstedRating"] = "New framework"

    output_path = DATA_DIR / "schools_processed.csv"
    schools.to_csv(output_path, index=False)
    print(f"\nSaved {len(schools)} schools to {output_path}")

    # Summary
    print("\nOfsted rating breakdown:")
    for rating, count in schools["OfstedRating"].value_counts().items():
        print(f"  {rating}: {count}")

    return schools


if __name__ == "__main__":
    gias_path = DATA_DIR / "edubasealldata.csv"
    ofsted_path = DATA_DIR / "ofsted_inspections.csv"
    process(gias_path, ofsted_path)
