import json

from utils.fetch_ugg import fetch_champ_counter_ugg


def extract_json_from_html(html: str, key: str) -> dict:
    """ Extract JSON from HTML using a key
        e.g. window.__SSR_DATA__ """
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
                    return json.loads(html[start:i + 1])
        escape = (c == "\\" and not escape)

    raise RuntimeError(f"No closing brace found for {key}")


def get_ssr_subdata(ssr: dict, suffix: str):
    """ Get first SSR block whose URL ends with given suffix """
    for url, block in ssr.items():
        if suffix in url:
            return block.get("data", {})
    raise KeyError(f"'{suffix}' not found in SSR data")


def get_champion_matchup_info(champion_specific_ssr: dict, role: str):
    """ Return all info about a matchup with enemy laner for given role.
    example output:
    000 = {dict: 17}
    {
        'carry_percentage_15': -140,
        'champion_id': 203,
        'cs_adv_15': -1,
        'duo_carry_percentage_15': 0,
        'duo_cs_adv_15': 0,
        'duo_gold_adv_15': 0,
        'duo_kill_adv_15': 0,
        'duo_xp_adv_15': 0,
        'gold_adv_15': 514,
        'jungle_cs_adv_15': 0,
        'kill_adv_15': 2,
        'matches': 1,
        'pick_rate': 0,
        'team_gold_difference_15': -485,
        'tier': {'pick_rate': 0, 'win_rate': 0},
        'win_rate': 0, 'xp_adv_15': 1158
    }
    """

    champ_id_to_name = {}
    for url, block in champion_specific_ssr.items():
        if "champion_id" in url:
            for cid, info in block["data"].items():
                champ_id_to_name[int(cid)] = info["name"]

    matchup_block = None
    for url, block in champion_specific_ssr.items():
        if "matchups" not in url:
            continue
        for key, value in block.get("data", {}).items():
            if key == get_rank_and_role_name(role):
                return value["counters"]
    if not matchup_block:
        raise RuntimeError("Lane matchup block not found")


def get_rank_and_role_name(role):
    return f"world_emerald_plus_{role.lower()}"


def parse_ugg_matchups(champion: str, role: str) -> dict[str, dict]:
    html = fetch_champ_counter_ugg(champion["slug"], role)
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
