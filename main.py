#!/usr/bin/env python3
import json, re
import os
import hashlib
import argparse, pathlib, re, sys, time
from typing import List, Tuple
import requests
from bs4 import BeautifulSoup
from tabulate import tabulate

CACHE_PERIOD = 60 * 60 * 24 * 3  # 3 days
CACHE_DIR = ".cache"
PARSED_CACHE_DIR = ".parsed_cache"
os.makedirs(PARSED_CACHE_DIR, exist_ok=True)

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
def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-").replace("'", ""))

def get_user_champ_pool(path: pathlib.Path) -> frozenset[str]:
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




def fetch_ugg(enemy: str, role: str, use_cache=True) -> str:
    if not use_cache:
        return _fetch_ugg_direct(enemy, role)

    os.makedirs(CACHE_DIR, exist_ok=True)
    key = f"{enemy.lower()}_{role.lower()}"
    path = os.path.join(CACHE_DIR, hashlib.md5(key.encode()).hexdigest() + ".html")

    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < CACHE_PERIOD:
        return open(path, "r", encoding="utf-8").read()

    html = _fetch_ugg_direct(enemy, role)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return html

def _fetch_ugg_direct(enemy, role):
    url = f"https://u.gg/lol/champions/{slugify(enemy)}/counter?role={role}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.text





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
            if key == get_rank_and_role_name("top"):
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

def load_parsed_ugg(enemy: str, role: str) -> dict[str, dict]:
    key = f"{enemy.lower()}_{role.lower()}"
    path = os.path.join(PARSED_CACHE_DIR, key + ".json")

    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < CACHE_PERIOD:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    html = fetch_ugg(enemy, role)
    parsed = parse_ugg(html)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(parsed, f)
    return parsed





def get_best_blindpick_ugg(role: str, pool: frozenset[str], meta_champs: frozenset[str], rank: str = "gold") -> list[tuple[str, float]]:
    scores = {}  # {champ_in_pool: [winrates vs each meta champ]}

    for enemy in meta_champs:
        try:
            pairs = load_parsed_ugg(enemy, role)
            for champ, stats in pairs.items():
                champ = champ.lower()
                if champ in pool:
                    scores.setdefault(champ, []).append(stats["wr"])
        except Exception:
            continue

    # Compute average winrate across meta champs matchups
    return sorted(
        [(champ.title(), sum(wrs)/len(wrs)) for champ, wrs in scores.items() if wrs],
        key=lambda x: -x[1]
    )


def get_least_bad_blindpick_ugg(role: str, pool: frozenset[str], meta_champs: frozenset[str]) -> list[tuple[str, float]]:
    scores = {}
    for enemy in meta_champs:
        try:
            pairs = load_parsed_ugg(enemy, role)
            for champ, stats in pairs.items():
                champ = champ.lower()
                if champ in pool:
                    scores.setdefault(champ, []).append(stats["wr"])
        except Exception:
            continue

    return sorted(
        [(champ.title(), min(wrs)) for champ, wrs in scores.items() if wrs],
        key=lambda x: -x[1]
    )


def get_rank_and_role_name(role):
    return f"world_emerald_plus_{role.lower()}"


def find_role_data(data: dict, role_key: str) -> dict:
    for block in data.values():
        if isinstance(block, dict):
            section = block.get("data")
            if isinstance(section, dict):
                role_data = section.get(role_key)
                if isinstance(role_data, dict):
                    return role_data
    return {}

def get_meta_champs_ugg(role: str, count: int = 15) -> frozenset[str]:
    """
    Get the top 'count' champs for a given role from U.GG,
    based on pickrate and winrate.
    """
    url = f"https://u.gg/lol/champions/yorick/counter?rank=emerald_plus&role={role.lower()}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"U.GG meta data HTTP {r.status_code}")

    data = extract_balanced_json(r.text, "window.__SSR_DATA__")

    champ_id_to_name = {}
    meta_stats = []

    for key, block in data.items():
        if "seo-champion-names.json" in key:
            champ_id_to_name = {
                int(cid): info.get("name")
                for cid, info in block.get("data", {}).items()
                if info.get("name")
            }
            break

    if not champ_id_to_name:
        raise RuntimeError("Champion ID-to-name map missing")

    role_key = get_rank_and_role_name(role)
    role_data = find_role_data(data, role_key)


    for champ in role_data.get("counters", []):
        cid = champ.get("champion_id")
        if cid is None or cid not in champ_id_to_name:
            continue

        name = champ_id_to_name[cid]
        win = champ.get("win_rate", 0)
        pick = champ.get("pick_rate", 0)
        tier = champ.get("tier", {})

        # score formula can be tuned
        score = (pick +
                (win - 50) * 0.25)
        meta_stats.append((name, score))

    print(f"Meta champs ({role_key}): {meta_stats}")
    if not meta_stats:
        raise RuntimeError("Meta stats not found or empty")

    meta_stats.sort(key=lambda x: -x[1])
    return {name for name, _ in meta_stats[:count]}


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--enemy")
    ap.add_argument("--role")
    ap.add_argument("--pool")
    ns, _ = ap.parse_known_args()
    prompt_missing(ns)

    pool = get_user_champ_pool(pathlib.Path(ns.pool))

    if not ns.enemy:
        # comparable to u.gg S tiers mostly
        meta_champs = get_meta_champs_ugg(ns.role)

        best = get_best_blindpick_ugg(ns.role, frozenset(pool), frozenset(meta_champs))
        print("\nBest blind-pick champs from your pool:")
        print(tabulate(best, headers=["Champion", "Avg WR vs Meta (%)"], floatfmt=".2f"))

        # doesn't lose badly into the most common meta champs
        least_bad = get_least_bad_blindpick_ugg(ns.role,pool,meta_champs)
        print("\nLeast bad blind-pick champs from your pool:")
        print(tabulate(least_bad, headers=["Champion", "Worst WR vs Meta (%)"], floatfmt=".2f"))
        return


    errors, pairs = [], []
    pairs = parse_ugg(fetch_ugg(ns.enemy, ns.role))
    if not pairs:
        sys.exit("source failed:\n  " + "\n  ".join(errors))
    filtered = [(c, v["wr"], v.get("gd15", "")) for c, v in pairs.items() if c.lower() in pool]

    if not filtered:
        print("None of your champions appear in the counter list.")
        return

    print(f"\nBest picks **from your pool** vs {ns.enemy.title()} ({ns.role})\n")

    print(tabulate(filtered, headers=[
        "Champion", f"Win-rate vs {ns.enemy.title()} (%)", f"Gold Ahead vs {ns.enemy.title()} @15"
    ], floatfmt=".2f"))
    print()



if __name__ == "__main__":
    main()
