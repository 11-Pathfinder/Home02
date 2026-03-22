"""Download school data from GIAS and Ofsted inspection outcomes."""

import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from config import GIAS_DOWNLOAD_URL

DATA_DIR = Path("data")

GIAS_BASE_URL = (
    "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public"
)

# Ofsted Management Information - latest inspections CSV
# This URL points to the GOV.UK page; we scrape the actual CSV link from it
OFSTED_MI_PAGE = (
    "https://www.gov.uk/government/statistical-data-sets/"
    "monthly-management-information-ofsteds-school-inspections-outcomes"
)


def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)


def download_gias_csv(force=False):
    """Download the GIAS edubasealldata CSV.

    Tries today's date first, then goes back up to 7 days to find
    the latest available file.
    """
    ensure_data_dir()
    output_path = DATA_DIR / "edubasealldata.csv"

    if output_path.exists() and not force:
        print(f"GIAS data already cached at {output_path}")
        return output_path

    # Try dated URLs first (most reliable)
    for days_back in range(8):
        date = datetime.now() - timedelta(days=days_back)
        date_str = date.strftime("%Y%m%d")
        url = f"{GIAS_BASE_URL}/edubasealldata{date_str}.csv"
        print(f"Trying GIAS download: {url}")

        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 200 and len(resp.content) > 1000:
                output_path.write_bytes(resp.content)
                print(f"Downloaded GIAS data ({len(resp.content) / 1e6:.1f} MB)")
                return output_path
        except requests.RequestException as e:
            print(f"  Failed: {e}")
            continue

    # Fallback to undated URL
    print(f"Trying undated URL: {GIAS_DOWNLOAD_URL}")
    resp = requests.get(GIAS_DOWNLOAD_URL, timeout=60)
    resp.raise_for_status()
    output_path.write_bytes(resp.content)
    print(f"Downloaded GIAS data ({len(resp.content) / 1e6:.1f} MB)")
    return output_path


def download_ofsted_csv(force=False, manual_url=None):
    """Download the Ofsted Management Information CSV.

    Downloads the cumulative 'state of the nation' CSV which contains the
    latest inspection outcome for ALL schools, not just recently-inspected ones.
    """
    ensure_data_dir()
    output_path = DATA_DIR / "ofsted_inspections.csv"

    if output_path.exists() and not force:
        print(f"Ofsted data already cached at {output_path}")
        return output_path

    # Allow manual URL override
    if manual_url:
        print(f"Using manually specified Ofsted URL: {manual_url}")
        resp = requests.get(manual_url, timeout=60)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
        print(f"Downloaded Ofsted data ({len(resp.content) / 1e6:.1f} MB)")
        return output_path

    # Fetch the MI page to find CSV download links
    print("Fetching Ofsted Management Information page...")
    resp = requests.get(OFSTED_MI_PAGE, timeout=30)
    resp.raise_for_status()

    # Extract all CSV links and their surrounding text for context
    # Pattern: capture link text and href together
    link_entries = re.findall(
        r'<a[^>]*href="([^"]*\.csv[^"]*)"[^>]*>([^<]*)</a>',
        resp.text,
        re.IGNORECASE,
    )
    # Also try href before text
    link_entries += re.findall(
        r'href="([^"]*\.csv[^"]*)"[^>]*>([^<]*)<',
        resp.text,
        re.IGNORECASE,
    )

    # Normalize URLs
    csv_entries = []
    seen_urls = set()
    for url, text in link_entries:
        if url.startswith("/"):
            url = f"https://www.gov.uk{url}"
        if url not in seen_urls:
            seen_urls.add(url)
            csv_entries.append((url, text.strip()))

    # Also find bare CSV links without anchor text
    bare_links = re.findall(
        r'href="(https://assets\.publishing\.service\.gov\.uk/[^"]*\.csv[^"]*)"',
        resp.text,
    )
    bare_gov = re.findall(
        r'href="(/government/uploads/[^"]*\.csv[^"]*)"', resp.text
    )
    for link in bare_links + [f"https://www.gov.uk{l}" for l in bare_gov]:
        if link not in seen_urls:
            seen_urls.add(link)
            csv_entries.append((link, ""))

    print(f"  Found {len(csv_entries)} CSV link(s) on the MI page:")
    for url, text in csv_entries:
        label = text if text else "(no link text)"
        print(f"    - {label}: {url}")

    # Prioritize: prefer the cumulative "state of the nation" / "as at" file
    # which contains ALL schools, over monthly files with only recent inspections.
    best_link = None
    best_reason = ""

    for url, text in csv_entries:
        combined = f"{text} {url}".lower()
        # "State of the nation" or "as at" = cumulative file with all schools
        if "state_of_the_nation" in combined.replace(" ", "_") or "as_at" in combined.replace(" ", "_"):
            best_link = url
            best_reason = "cumulative 'state of the nation' / 'as at' file"
            break

    # Fallback: look for "latest inspection" in URL or text
    if not best_link:
        for url, text in csv_entries:
            combined = f"{text} {url}".lower().replace("_", " ")
            if "latest inspection" in combined:
                best_link = url
                best_reason = "'latest inspection' file"
                break

    # Fallback: look for "most recent"
    if not best_link:
        for url, text in csv_entries:
            combined = f"{text} {url}".lower()
            if "most_recent" in combined or "most recent" in combined:
                best_link = url
                best_reason = "'most recent' file"
                break

    # Last resort: pick the first CSV
    if not best_link and csv_entries:
        best_link = csv_entries[0][0]
        best_reason = "first available CSV (fallback)"

    if not best_link:
        print("ERROR: Could not find any CSV download links on the Ofsted MI page.")
        print("You may need to manually download the CSV and specify it with --ofsted-url.")
        print(f"  Page: {OFSTED_MI_PAGE}")
        print(f"  Place it at: {output_path}")
        return None

    print(f"  Selected: {best_reason}")
    print(f"Downloading Ofsted data from: {best_link}")
    resp = requests.get(best_link, timeout=60)
    resp.raise_for_status()
    output_path.write_bytes(resp.content)
    size_mb = len(resp.content) / 1e6
    print(f"Downloaded Ofsted data ({size_mb:.1f} MB)")

    # Validate: the cumulative file should be several MB with thousands of rows
    row_count = resp.text.count('\n')
    if row_count < 1000:
        print(f"  WARNING: Downloaded file has only ~{row_count} rows.")
        print("  This may be a monthly file rather than the cumulative file.")
        print("  Schools inspected years ago may be missing.")
        print(f"  Try specifying the URL manually with --ofsted-url")

    return output_path


def fetch_legacy_rating(urn):
    """Fetch a school's current Ofsted rating from the Ofsted website.

    Used for schools with "Standards maintained" outcomes where the legacy
    rating isn't in the MI CSV data.

    Returns:
        str: Rating ('Outstanding', 'Good', etc.) or None if not found.
    """
    url = f"https://reports.ofsted.gov.uk/provider/21/{urn}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return None

        # The current rating has class "rating--selected"
        match = re.search(
            r'class="rating\s+rating--selected[^"]*"[^>]*>\s*<span>([^<]+)</span>',
            resp.text,
        )
        if match:
            rating = match.group(1).strip()
            # Normalize rating names
            rating_map = {
                "Outstanding": "Outstanding",
                "Good": "Good",
                "Requires Improvement": "Requires improvement",
                "Requires improvement": "Requires improvement",
                "Inadequate": "Inadequate",
            }
            return rating_map.get(rating, rating)
        return None
    except requests.RequestException:
        return None


def fetch_legacy_ratings(urns, force=False, delay=0.2):
    """Fetch legacy ratings for multiple schools from Ofsted website.

    Caches results to data/legacy_ratings.csv to avoid re-fetching.

    Args:
        urns: List of URNs to fetch ratings for.
        force: If True, re-fetch all ratings even if cached.
        delay: Seconds to wait between requests (be nice to Ofsted servers).

    Returns:
        DataFrame with URN and OfstedRating columns.
    """
    ensure_data_dir()
    cache_path = DATA_DIR / "legacy_ratings.csv"

    # Load existing cache
    cached = {}
    if cache_path.exists() and not force:
        df = pd.read_csv(cache_path)
        cached = dict(zip(df["URN"].astype(int), df["OfstedRating"]))
        print(f"  Loaded {len(cached)} cached legacy ratings")

    # Find URNs that need fetching
    urns_to_fetch = [u for u in urns if int(u) not in cached]

    if not urns_to_fetch:
        print("  All legacy ratings already cached")
        return pd.DataFrame({"URN": list(cached.keys()), "OfstedRating": list(cached.values())})

    print(f"  Fetching {len(urns_to_fetch)} legacy ratings from Ofsted website...")
    fetched = 0
    failed = 0

    for i, urn in enumerate(urns_to_fetch):
        rating = fetch_legacy_rating(urn)
        if rating:
            cached[int(urn)] = rating
            fetched += 1
        else:
            failed += 1

        # Progress update every 50 schools
        if (i + 1) % 50 == 0:
            print(f"    Progress: {i + 1}/{len(urns_to_fetch)} (fetched: {fetched}, failed: {failed})")

        # Be nice to Ofsted servers
        if delay > 0 and i < len(urns_to_fetch) - 1:
            time.sleep(delay)

    print(f"  Completed: {fetched} ratings fetched, {failed} not found")

    # Save updated cache
    result = pd.DataFrame({"URN": list(cached.keys()), "OfstedRating": list(cached.values())})
    result.to_csv(cache_path, index=False)
    print(f"  Saved {len(result)} legacy ratings to {cache_path}")

    return result


def fetch_all(force=False, ofsted_url=None):
    """Download all required data files."""
    gias_path = download_gias_csv(force=force)
    ofsted_path = download_ofsted_csv(force=force, manual_url=ofsted_url)
    return gias_path, ofsted_path


if __name__ == "__main__":
    fetch_all()
