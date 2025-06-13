import argparse, pathlib, sys
from tabulate import tabulate

from lol_api_tester import get_champs_in_teams_in_local_champ_select
from utils.parse_ugg_ssr import parse_ugg_matchups
from utils.champion_names import load_champ_name_map, get_champ_name_variations

CACHE_BOOL = True  # change if needed

def get_user_champ_pool(path: pathlib.Path) -> frozenset[str]:
    if not path.exists():
        sys.exit(f"champion-pool file '{path}' not found")
    return {c.strip().lower() for c in path.read_text().splitlines() if c.strip()}


def main():
    CHAMP_NAME_MAP = load_champ_name_map()
    args = argParser()
    enemy = args.enemy


    if not enemy:
        # enemy = get_champ_name_variations(input("Enemy champion: ").strip(), CHAMP_NAME_MAP)
        enemy = get_champ_name_variations(getEnemyLaner().strip(), CHAMP_NAME_MAP)


    pool = get_user_champ_pool(pathlib.Path(args.pool))

    matchup_data = parse_ugg_matchups(enemy, args.role)

    filtered = [
        (champ, data["wr"], data["gd15"],data["matches"]) for champ, data in matchup_data.items()
        if champ.lower() in pool
    ]

    enemy_name = enemy["name"]
    if not filtered:
        print(f"None of your champions appear in the counter list for {enemy_name}.")
        return

    printPoolWinrateSummary(args, enemy_name, filtered)


def argParser():
    ap = argparse.ArgumentParser(description="Counterpick tool")
    ap.add_argument("--enemy", required=False, help="Enemy champion name")
    ap.add_argument("--role", default="top", help="Role (default: top)")
    ap.add_argument("--pool", default="champion_pool.txt", help="Path to your champion pool file")
    args = ap.parse_args()
    return args


def printPoolWinrateSummary(args, enemy_name, filtered):
    print(f"\nBest picks **from your pool** vs {enemy_name} ({args.role})\n")
    print(tabulate(
        filtered,
        headers=["Champion", f"WR % vs {enemy_name} ", "Gold Adv @15", "Matches"],
        floatfmt=".2f"
    ))
    print("\nMap reminder:\nhttps://youtu.be/lYmgW4UkyZU?si=e8P8j_0xkm0IcT_m")

def getEnemyLaner():
    enemy_champs = get_champs_in_teams_in_local_champ_select()['enemyChamps']
    #     print enemy champs+ assign each a number 1 to 5
    for i, champ in enumerate(enemy_champs, start=1):
        print(f"{i}. {champ}")
    #  ask user to pick a number of who they think is the enemy laner
    print("Pick a number for the enemy laner:")
    try:
        choice = int(input())
        if 1 <= choice <= len(enemy_champs):
            enemy_laner = enemy_champs[choice - 1]
            print(f"You picked: {enemy_laner}")
        else:
            print("Invalid choice. Please pick a number from the list.")
    except ValueError:
        print("Invalid input. Please enter a number.")

    return enemy_laner


if __name__ == "__main__":
    main()
