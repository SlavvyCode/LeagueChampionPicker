#!/usr/bin/env python3
"""
lol_counter_live.py – live counter-pick helper filtered to your champion pool.

Highlights
----------
• Fetches U.GG first; if that fails, falls back to LoLalytics (or vice-versa via --source).
• For LoLalytics the displayed number is the ENEMY champ's win-rate; we invert it so
  you see *your* champ’s win-rate vs the enemy (labelled accordingly).

Usage
-----
python lol_counter_live.py --enemy Yorick                # ask for lane & pool file
python lol_counter_live.py --enemy Quinn --role top --pool pool.txt
python lol_counter_live.py --enemy Darius --source lolalytics
"""

import argparse, pathlib, re, sys, time
from typing import List, Tuple
import requests
from bs4 import BeautifulSoup
from tabulate import tabulate
OPGG_SLUGS = {
    "cho'gath": "chogath",
    "k'sante": "ksante",
    "ksante": "ksante",
    "dr. mundo": "drmundo",
    "lee sin": "leesin",
    "tahm kench": "tahmkench",
    "tahm": "tahmkench",
    "twisted fate": "twistedfate",
    "miss fortune": "missfortune",
    "master yi": "masteryi",
    "jarvan iv": "jarvaniv",
    "renata glasc": "renata",
    "bel'veth": "belveth",
    "kai'sa": "kaisa",
    "vel'koz": "velkoz",
    "velkoz": "velkoz",
    "nunu & willump": "nunu",
    "rek'sai": "reksai",
    "kha'zix": "khazix",
    "leblanc": "leblanc",
    "xin zhao": "xinzhao",
    "aurelion sol": "aurelionsol",
    "yuumi": "yuumi",
}


def slugify_for_opgg(name: str) -> str:
    return OPGG_SLUGS.get(name, name.lower().replace(" ", "").replace("'", "").replace(".", ""))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://u.gg/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

LANE_KEYS = {
    "gd10":  ("goldDiff10",   100),   # stored as +123 gold
    "xpd10": ("xpDiff10",     1),     # stored as +95 xp
    "csd15": ("csDiff15",     1),     # stored as +12 cs
    "solokill": ("soloKills", 100),   # stored as 0.0823  → 8.23 %
}

def parse_lolalytics_adv(html: str) -> dict[str, dict]:
    """
    Return  {champ: {'wr': 53.2, 'gd10': 240, 'xpd10': 120, ...}}
    """
    soup = BeautifulSoup(html, "html.parser")
    blob = soup.find("script", id="__NEXT_DATA__")
    if not blob:
        raise RuntimeError("No NEXT_DATA in LoLalytics page")

    data = json.loads(blob.string)
    out = {}

    # the counters array sits at props.pageProps.data.counters
    counters = (
        data["props"]["pageProps"]["data"]["counters"]
        if "props" in data else []
    )
    for entry in counters:
        champ = entry["key"]
        win   = round(entry["winRate"] * 100, 2)        # 0.524 → 52.4 %
        stats = {"wr": win}
        for label, (json_key, scale) in LANE_KEYS.items():
            raw = entry.get(json_key)
            if raw is not None:
                stats[label] = round(raw * scale, 2)
        out[champ] = stats
    return out

def lane_score(d):          # d is one champ’s dict from step 2
    # simple weighted model – tweak to taste
    return (
            (d.get("gd10", 0) / 100)   +      #  +1 per 100 g
            (d.get("xpd10", 0) / 100)  +      #  +1 per 100 xp
            (d.get("csd15", 0) * 0.1)  +      #  +0.1 per CS
            (d.get("solokill", 0) * 0.5)      #  +0.5 per 1 % solo-kill
    )

# ------------------------------------------------ helpers
def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-").replace("'", ""))

def load_pool(path: pathlib.Path) -> set[str]:
    if not path.exists():
        sys.exit(f"champion-pool file '{path}' not found")
    return {c.strip().lower() for c in path.read_text().splitlines() if c.strip()}

def prompt_missing(ns):
    if not ns.enemy:
        ns.enemy = input("Enemy champion: ").strip()
    # if not ns.role:
    #     ns.role = input("Role (top/jungle/mid/bot/support) [top]: ").strip() or "top"
    # if not ns.pool:
    #     d = "champion_pool.txt"
    #     ns.pool = input(f"Champion-pool file [{d}]: ").strip() or d
        ns.role = "top"
        ns.pool = "champion_pool.txt"




# ------------------------------------------------ U.GG
def fetch_ugg(enemy: str, role: str) -> str:
    url = f"https://u.gg/lol/champions/{slugify(enemy)}/counter?role={role}"

    r = requests.get(url, headers=HEADERS, timeout=10)

    if r.status_code != 200:
        raise RuntimeError(f"U.GG HTTP {r.status_code}")
    return r.text

import json, re
from typing import List, Tuple
from bs4 import BeautifulSoup

def _walk_json(node, out):
    """Depth-first search through a nested JSON tree.
       Collect (champ, winRate) pairs when we see them."""
    if isinstance(node, dict):
        if "championName" in node and "winRate" in node:
            champ = node["championName"].strip()
            wr    = node["winRate"] * 100          # 0.5862 → 58.62
            out.append((champ, round(wr, 2)))
        for v in node.values():
            _walk_json(v, out)
    elif isinstance(node, list):
        for item in node:
            _walk_json(item, out)

def extract_balanced_json(html: str, key: str) -> dict:
    start = html.find(key)
    if start == -1:
        raise RuntimeError(f"{key} not found")

    start = html.find("{", start)
    if start == -1:
        raise RuntimeError(f"No opening brace after {key}")

    brace_count = 0
    in_str = False
    escape = False

    for i in range(start, len(html)):
        c = html[i]
        if c == '"' and not escape:
            in_str = not in_str
        elif not in_str:
            if c == "{":
                brace_count += 1
            elif c == "}":
                brace_count -= 1
                if brace_count == 0:
                    try:
                        return json.loads(html[start:i+1])
                    except json.JSONDecodeError as e:
                        raise RuntimeError(f"JSON parsing error: {e}")
        escape = (c == "\\" and not escape)

    raise RuntimeError(f"No closing brace found for {key}")



def extract_lane_matchups(ssr_data: dict) -> list[tuple[str, float, float]]:
    champ_id_to_name = {}

    for url, block in ssr_data.items():
        if "seo-champion-names.json" in url:
            for cid, info in block["data"].items():
                champ_id_to_name[int(cid)] = info["name"]

    matchup_block = None
    for url, block in ssr_data.items():
        if "matchups" not in url:
            continue
        for key, value in block.get("data", {}).items():
            if key == "world_emerald_plus_top":
                matchup_block = value["counters"]
    if not matchup_block:
        raise RuntimeError("Lane matchup block not found")

    return sorted([
        (
            champ_id_to_name.get(c["champion_id"], f"#{c['champion_id']}"),
            round(100 - c.get("win_rate", 0), 2),
            round(-c.get("gold_adv_15", 0), 2)
        )
        for c in matchup_block if "gold_adv_15" in c
    ], key=lambda x: -x[1])


def parse_ugg(html: str) -> dict[str, dict]:
    ssr = extract_balanced_json(html, "window.__SSR_DATA__")

    raw_pairs = extract_lane_matchups(ssr)
    return {
        champ: {"wr": wr, "gd15": gd}
        for champ, wr, gd in raw_pairs
    }



def _dfs_extract_counters(node, out):
    """
    Depth-first walk through u.gg __NEXT_DATA__ JSON to find counters.
    Looks for championName + winRate float (0.5325 = 53.25%).
    """
    if isinstance(node, dict):
        if "championName" in node and "winRate" in node:
            name = node["championName"]
            wr = node["winRate"]
            if isinstance(name, str) and isinstance(wr, (int, float)):
                out.append((name.strip(), round(wr * 100, 2)))
        for val in node.values():
            _dfs_extract_counters(val, out)
    elif isinstance(node, list):
        for item in node:
            _dfs_extract_counters(item, out)


# ------------------------------------------------ LoLalytics
def fetch_lolalytics(enemy: str, role: str) -> str:
    url = f"https://lolalytics.com/lol/{slugify(enemy)}/counters/"
    if role.lower() != "top":
        url += f"?lane={role.lower()}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"LoLalytics HTTP {r.status_code}")
    return r.text

def parse_lolalytics(html: str) -> List[Tuple[str, float]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    # each card has champion name + win-rate (enemy's) in a green span
    for card in soup.select('div[class*="h-[254px]"]'):
        name_div = card.find("div", class_=re.compile(r"text-\[15px\]"))
        wr_div = card.find("div", class_=re.compile(r"text-green-300"))
        if name_div and wr_div:
            champ = name_div.text.strip()
            enemy_wr = float(re.search(r"([\d.]+)", wr_div.text).group(1))
            my_wr = round(100.0 - enemy_wr, 2)  # invert
            rows.append((champ, my_wr))
    if not rows:
        raise RuntimeError("LoLalytics layout changed (no cards)")
    return rows


import requests
from bs4 import BeautifulSoup
from typing import List, Tuple
import re

def parse_opgg(html: str) -> List[Tuple[str, float]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for li in soup.select("ul > li"):
        champ_tag = li.find("img", alt=True)
        wr_tag = li.find("strong", class_=re.compile(r"text-.*"))

        if champ_tag and wr_tag:
            champ = champ_tag["alt"].strip()
            wr_match = re.search(r"([\d.]+)%", wr_tag.text)
            if wr_match:
                enemy_wr = float(wr_match.group(1))
                my_wr = round(100 - enemy_wr, 2)
                rows.append((champ, my_wr))

    if not rows:
        raise RuntimeError("OP.GG: No valid counters found")
    return sorted(rows, key=lambda x: -x[1])  # sort by your winrate descending


# ------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--enemy")
    ap.add_argument("--role")
    ap.add_argument("--pool")
    ap.add_argument("--source", choices=["ugg", "lolalytics", "auto"], default="auto",
                    help="preferred site (auto → U.GG then LoLalytics)")
    ns, _ = ap.parse_known_args()
    prompt_missing(ns)

    pool = load_pool(pathlib.Path(ns.pool))
    errors, pairs = [], []
    order = ["ugg","opgg", "lolalytics"] if ns.source == "auto" else [ns.source]

    for site in order:
        try:

            # if site == "opgg":
            #     url = f"https://op.gg/lol/champions/{slugify_for_opgg(ns.enemy)}/counters/{ns.role}"
            #
            #     html = requests.get(
            #         url,
            #         headers=HEADERS,
            #         timeout=10
            #     ).text
            #     pairs = parse_opgg(html)
            # elif site == "lolalytics":
            #     pairs = parse_lolalytics(fetch_lolalytics(ns.enemy, ns.role))
            # elif site == "ugg":
            pairs = parse_ugg(fetch_ugg(ns.enemy, ns.role))
            break;
        except Exception as e:
            errors.append(f"{site}: {e}")
            time.sleep(0.3)

    if not pairs:
        sys.exit("All sources failed:\n  " + "\n  ".join(errors))

    # filtered = [(c, w) for c, w in pairs if c.lower() in pool]

    #  if exists?
    filtered = [(c, v["wr"], v.get("gd15", "")) for c, v in pairs.items() if c.lower() in pool]

    if not filtered:
        print("None of your champions appear in the counter list.")
        return

    print(f"\nBest picks **from your pool** vs {ns.enemy.title()} ({ns.role})\n")

    print(tabulate(filtered, headers=[
        "Champion", f"Win-rate vs {ns.enemy.title()} (%)", "GD@15"
    ], floatfmt=".2f"))
    # print(tabulate(filtered, headers=[ "Champion",
    #                                    f"Win-rate vs {ns.enemy.title()} (%)" ],
    #                floatfmt=".2f"))
    print()



if __name__ == "__main__":
    main()
