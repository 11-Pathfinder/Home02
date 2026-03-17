"""Download school data from GIAS and Ofsted inspection outcomes."""

import os
from datetime import datetime, timedelta
from pathlib import Path

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


def download_ofsted_csv(force=False):
    """Download the Ofsted Management Information CSV.

    Downloads the 'latest inspections' CSV which contains the most recent
    inspection outcome for each school.
    """
    ensure_data_dir()
    output_path = DATA_DIR / "ofsted_inspections.csv"

    if output_path.exists() and not force:
        print(f"Ofsted data already cached at {output_path}")
        return output_path

    # Fetch the MI page to find CSV download links
    print("Fetching Ofsted Management Information page...")
    resp = requests.get(OFSTED_MI_PAGE, timeout=30)
    resp.raise_for_status()

    # Look for CSV links in the page content
    import re

    # Find links to CSV files on assets.publishing.service.gov.uk
    csv_links = re.findall(
        r'href="(https://assets\.publishing\.service\.gov\.uk/[^"]*\.csv[^"]*)"',
        resp.text,
    )

    # Also check for links via /government/uploads pattern
    gov_links = re.findall(
        r'href="(/government/uploads/[^"]*\.csv[^"]*)"', resp.text
    )
    csv_links.extend(
        f"https://www.gov.uk{link}" for link in gov_links
    )

    # Prefer the "latest inspections" file
    latest_link = None
    for link in csv_links:
        if "latest_inspection" in link.lower() or "latest inspection" in link.lower().replace("_", " "):
            latest_link = link
            break

    # If no "latest" found, try "most recent" or just use the largest CSV
    if not latest_link:
        for link in csv_links:
            if "most_recent" in link.lower():
                latest_link = link
                break

    if not latest_link and csv_links:
        # Use the first CSV link as fallback
        latest_link = csv_links[0]
        print(f"Warning: Could not identify 'latest inspections' CSV, using: {latest_link}")

    if not latest_link:
        print("ERROR: Could not find any CSV download links on the Ofsted MI page.")
        print("You may need to manually download the CSV from:")
        print(f"  {OFSTED_MI_PAGE}")
        print(f"Place it at: {output_path}")
        return None

    print(f"Downloading Ofsted data from: {latest_link}")
    resp = requests.get(latest_link, timeout=60)
    resp.raise_for_status()
    output_path.write_bytes(resp.content)
    print(f"Downloaded Ofsted data ({len(resp.content) / 1e6:.1f} MB)")
    return output_path


def fetch_all(force=False):
    """Download all required data files."""
    gias_path = download_gias_csv(force=force)
    ofsted_path = download_ofsted_csv(force=force)
    return gias_path, ofsted_path


if __name__ == "__main__":
    fetch_all()
