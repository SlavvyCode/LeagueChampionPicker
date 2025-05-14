import os
import re
import json
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

PATCH_META_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://u.gg/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def get_latest_patches(count=2) -> list[str]:
    """Get the latest patches from Data Dragon API."""
    try:
        response = requests.get(PATCH_META_URL, headers=HEADERS, timeout=10)
        all_patches = response.json()

        # Filter to only include standard patch formats (X.Y)
        standard_patches = []
        seen_major_minor = set()

        for patch in all_patches:
            # Skip non-standard formats like "lolpatch_x"
            if patch.startswith("lolpatch_"):
                continue

            # Extract major.minor version
            parts = patch.split('.')
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                major_minor = f"{parts[0]}.{parts[1]}"
                if major_minor not in seen_major_minor:
                    standard_patches.append(patch)
                    seen_major_minor.add(major_minor)

                    # Break once we have enough patches
                    if len(standard_patches) >= count:
                        break

        return standard_patches[:count]
    except Exception as e:
        print(f"Error fetching patches: {e}")
        return []

def convert_to_client_version(ddragon_version: str) -> str:
    """
    Convert Data Dragon version to client-facing version.
    For modern patches, this is typically adding 10 to the major version.
    """
    parts = ddragon_version.split('.')
    if len(parts) >= 2 and parts[0].isdigit():
        major = int(parts[0])
        # Modern LoL client versions are typically Data Dragon version + 10
        client_major = major + 10
        return f"{client_major}.{parts[1]}"
    return ddragon_version

def get_patch_release_dates() -> dict[str, str]:
    """
    Scrapes League of Legends patch release dates from the official website.

    Returns:
        A dictionary mapping patch numbers (e.g., "25.10") to their release dates
        in YYYY-MM-DD format
    """
    patches = {}

    try:
        url = "https://support-leagueoflegends.riotgames.com/hc/en-us/articles/360018987893-Patch-Schedule-League-of-Legends"
        response = requests.get(url, headers=HEADERS, timeout=10)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the patch schedule table
            tables = soup.find_all('table')
            patch_table = None

            for table in tables:
                if table.find('td', string=re.compile(r'\d+\.\d+')):
                    patch_table = table
                    break

            if patch_table:
                rows = patch_table.find_all('tr')

                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        # Extract patch number
                        patch_cell = cells[0].text.strip()
                        if not re.match(r'\d+\.\d+', patch_cell):
                            continue

                        # Extract date
                        date_cell = cells[1].text.strip()

                        # Try different date formats
                        date_formats = [
                            "%B %d, %Y",           # January 9, 2025
                            "%B %d, %Y (%A)",      # January 9, 2025 (Thursday)
                            "%d %B %Y",            # 9 January 2025
                            "%B %d"                # January 9 (no year)
                        ]

                        parsed_date = None
                        for fmt in date_formats:
                            try:
                                date_str = date_cell
                                # Handle dates without year by adding current year
                                if "year" not in fmt and not re.search(r'\d{4}', date_cell):
                                    current_year = datetime.now().year
                                    date_str = f"{date_cell}, {current_year}"
                                    fmt = "%B %d, %Y"

                                parsed_date = datetime.strptime(date_str, fmt)
                                break
                            except ValueError:
                                continue

                        if parsed_date:
                            patches[patch_cell] = parsed_date.strftime("%Y-%m-%d")
                        else:
                            print(f"Could not parse date: '{date_cell}'")

    except Exception as e:
        print(f"Error scraping patch schedule: {e}")

    return patches

def estimate_release_dates(patches: list[str]) -> dict[str, dict]:
    result = {}

    # Try to get actual release dates first
    actual_dates = get_patch_release_dates()

    # League patches typically come out on Wednesdays
    current_date = datetime.now()
    days_since_wednesday = (current_date.weekday() - 2) % 7
    last_wednesday = current_date - timedelta(days=days_since_wednesday)

    release_date = last_wednesday

    for i, patch in enumerate(patches):
        client_version = convert_to_client_version(patch)

        # Try to find actual date first, fall back to estimation
        patch_key = ".".join(patch.split('.')[:2])  # Get just major.minor version
        actual_date = actual_dates.get(patch_key)

        result[patch] = {
            "ddragon_version": patch,
            "client_version": client_version,
            "release_date": actual_date if actual_date else release_date.strftime("%Y-%m-%d"),
            "is_estimated": not bool(actual_date)
        }

        # Go back two weeks for the previous patch
        if i < len(patches) - 1:
            release_date -= timedelta(days=14)

    return result

def get_effective_patch() -> str:
    # Get the latest patches
    latest_patches = get_latest_patches(2)
    if not latest_patches:
        return ""

    current_patch = latest_patches[0]
    patch_info = estimate_release_dates(latest_patches)

    # Get the release date for current patch
    current_patch_info = patch_info.get(current_patch, {})
    release_date_str = current_patch_info.get("release_date")

    if not release_date_str:
        return current_patch  # fallback to current if unknown

    try:
        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        today = datetime.now().date()

        # todo amend?
        if today - release_date < timedelta(days=3):
            # If current patch is too new, return the previous one
            if len(latest_patches) > 1:
                return latest_patches[1]
    except ValueError:
        pass  # Date parsing failed

    return current_patch

def can_use_latest_patch() -> bool:
    """Check if we can use the latest patch (not too new)."""
    current_patch = get_latest_patches(1)
    if not current_patch:
        return False
    return get_effective_patch() == current_patch[0]
def get_current_patch() -> str:
    """Get the current patch version."""
    latest_patches = get_latest_patches(1)
    if latest_patches:
        return latest_patches[0]
    return ""


def main():
    print("Fetching latest League of Legends patches...")
    latest_patches = get_latest_patches(2)

    if not latest_patches:
        print("Failed to fetch patch information.")
        return

    print(f"\nFound latest patches: {latest_patches}")

    patch_info = estimate_release_dates(latest_patches)
    effective_patch = get_effective_patch()

    print("\nPatch information:")
    for ddragon_ver, info in patch_info.items():
        print(f"Data Dragon: {ddragon_ver}")
        print(f"Client Version: {info['client_version']}")
        print(f"Release Date: {info['release_date']} {'(estimated)' if info['is_estimated'] else ''}")
        print()

    print(f"\nEffective patch to use: {effective_patch}")
    print(f"Can use latest patch: {can_use_latest_patch()}")
    os.makedirs("./cache", exist_ok=True)
    # Save to file
    with open("../cache/latest_patches.json", "w") as f:
        json.dump({
            "patches": patch_info,
            "effective_patch": effective_patch,
            "can_use_latest": can_use_latest_patch()
        }, f, indent=2)
    print("\nSaved patch information to latest_patches.json")

if __name__ == "__main__":
    main()