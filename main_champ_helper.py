import time, os, json, hashlib, requests
import httpx
from selectolax.parser import HTMLParser
from pathlib import Path
from typing import Dict, Tuple, List, FrozenSet
from playwright.sync_api import sync_playwright
import time

import httpx

from utils.fetch_ugg import HEADERS
from utils.parse_ugg_ssr import extract_json_from_html, parse_ugg_matchups
from requests_html import HTMLSession

def get_global_pickrates(ssr: dict) -> dict[int, float]:
    """champ-id -> global pick-rate across all roles (emerald+)."""
    for url, blk in ssr.items():
        if "world_emerald_plus_top" in url or "ranked_solo_5x5/all" in url:
            return {c["champion_id"]: c.get("pick_rate", 0.0)
                    for c in blk["data"].get("counters", [])}
    return {}

def get_role_meta_pickrates(role: str) -> dict[str, float]:
    url = f"https://u.gg/lol/champions/aatrox/counter?rank=emerald_plus&role={role}"
    ssr = extract_json_from_html(url, "window.__SSR_DATA__")

    # champ-id  →  name
    id2name = next(
        blk["data"]                            # safe: this block is always a dict
        for u, blk in ssr.items() if "seo-champion-names.json" in u
    )
    id2name = {int(cid): info["name"].lower() for cid, info in id2name.items()}

    global_pk = get_global_pickrates(ssr)      # as in the previous message
    role_pk   = {}

    role_key = f"world_emerald_plus_{role.lower()}"

    for blk in ssr.values():
        if not isinstance(blk, dict):          # ← **skip list blocks**
            continue
        data_section = blk.get("data")
        if not isinstance(data_section, dict):
            continue
        rdata = data_section.get(role_key)
        if not isinstance(rdata, dict):
            continue

        for c in rdata.get("counters", []):
            cid = c["champion_id"]
            role_pk[id2name[cid]] = c.get("pick_rate", 0.0)
        break                                  # we found the block, stop looping

    # fall-back to global pick-rate when lane pick-rate is zero / missing
    return {name: (role_pk.get(name, 0.0) or global_pk.get(cid, 0.0))
            for cid, name in id2name.items()}


# --------------------------------------------------------------------
def get_best_blind_bans_as_champion(main_champ: str,
                                    role: str,
                                    count: int = 5) -> list[tuple[str,float,float]]:
    """(champ, my WR vs them, THEIR global pick-rate)"""
    counters   = parse_ugg_matchups(main_champ, role)
    pickrates  = get_role_meta_pickrates(role)          # use new function above

    bad = []
    for enemy, stats in counters.items():
        wr = stats["wr"]                # ← already our win-rate vs them
        pk = pickrates.get(enemy.lower(), 0.0)
        if wr > 50 and pk:              # ignore fringe picks completely
            score = (50 - wr) + pk*0.6  # tweak weight as you like
            bad.append((enemy.title(), wr, pk, score))

    bad.sort(key=lambda x: -x[3])
    return [(e, wr, pk) for e, wr, pk, _ in bad[:count]]



ROLES = ["top-lane", "jungle", "mid-lane", "adc", "support"]



def scrape_ugg_tiers():
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Intercept network requests
            real_data_url = None




            page.goto("https://u.gg/lol/tier-list", wait_until="networkidle")
            browser.close()

            if real_data_url:
                response = requests.get(real_data_url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://u.gg/"
                })
                return response.json()  # Contains clean tier list data


if __name__ == "__main__":
    data = scrape_ugg_tiers()
    print(data)