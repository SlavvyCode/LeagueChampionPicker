import argparse, pathlib, sys
from tabulate import tabulate
from utils.fetch import fetch_ugg
from utils.parse_ssr import extract_json_from_html, get_champion_matchup_info, get_ssr_subdata
from utils.champions import load_champ_name_map, get_champ_name_variations

CACHE_BOOL = True  # change if needed

def get_user_champ_pool(path: pathlib.Path) -> frozenset[str]:
    if not path.exists():
        sys.exit(f"champion-pool file '{path}' not found")
    return {c.strip().lower() for c in path.read_text().splitlines() if c.strip()}

def parse_ugg_matchups(champion: str, role: str) -> dict[str, dict]:
    html = fetch_ugg(champion["slug"], role)
    ssr = extract_json_from_html(html, "window.__SSR_DATA__")
    champ_data = get_ssr_subdata(ssr, "en_US/champion.json")


    champ_id_to_name = {int(info["key"]): info["name"] for info in champ_data.values()}

    matchups = get_champion_matchup_info(ssr, role)

    return {
        champ_id_to_name.get(c["champion_id"], f"#{c['champion_id']}"): {
            "wr": round(100 - c.get("win_rate", 0), 2),
            "gd15": round(-c.get("gold_adv_15", 0), 2),
            "pickrate": round(c.get("pick_rate", 0), 2),
            "matches": c.get("matches", 0),
        }
        for c in matchups if "gold_adv_15" in c
    }


def main():
    CHAMP_NAME_MAP = load_champ_name_map()

    ap = argparse.ArgumentParser(description="Counterpick tool")
    ap.add_argument("--enemy", required=False, help="Enemy champion name")
    ap.add_argument("--role", default="top", help="Role (default: top)")
    ap.add_argument("--pool", default="champion_pool.txt", help="Path to your champion pool file")
    args = ap.parse_args()

    if not args.enemy:
        args.enemy = get_champ_name_variations(input("Enemy champion: ").strip(), CHAMP_NAME_MAP)

    pool = get_user_champ_pool(pathlib.Path(args.pool))


    matchup_data = parse_ugg_matchups(args.enemy, args.role)

    filtered = [
        (champ, data["wr"], data["gd15"],data["matches"]) for champ, data in matchup_data.items()
        if champ.lower() in pool
    ]

    enemy_name = args.enemy["name"]
    if not filtered:
        print(f"None of your champions appear in the counter list for {enemy_name}.")
        return

    print(f"\nBest picks **from your pool** vs {enemy_name} ({args.role})\n")
    print(tabulate(
        filtered,
        headers=["Champion", f"WR % vs {enemy_name} ", "Gold Adv @15", "Matches"],
        floatfmt=".2f"
    ))

if __name__ == "__main__":
    main()
