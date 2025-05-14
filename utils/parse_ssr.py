import json

def extract_json_from_html(html: str, key: str) -> dict:
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
                    return json.loads(html[start:i+1])
        escape = (c == "\\" and not escape)

    raise RuntimeError(f"No closing brace found for {key}")

def get_ssr_subdata(ssr: dict, suffix: str):
    """ Get first SSR block whose URL ends with given suffix """
    for url, block in ssr.items():
        if suffix in url:
            return block.get("data", {})
    raise KeyError(f"'{suffix}' not found in SSR data")

def get_champion_matchup_info(champion_specific_ssr: dict, role: str):
    """ Return counters block from SSR for given role_key """
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