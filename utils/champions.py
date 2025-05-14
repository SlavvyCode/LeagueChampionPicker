import re, json
import requests
from .fetch import fetch_ugg
from .parse_ssr import extract_json_from_html, get_ssr_subdata
import difflib
from utils.patch import get_current_patch


PATCH_META_URL = "https://ddragon.leagueoflegends.com/api/versions.json"

def normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())

def load_champ_name_map() -> dict[str, dict]:
    current_version = get_current_patch()
    cache_path = "./cache/champ_alias_map.json"
    version_path = "./cache/champ_alias_map.version"

    try:
        cached_version = open(version_path).read().strip()
        if cached_version == current_version:
            return json.load(open(cache_path))
    except:
        pass  # cache miss

    # champion irrelevant to get this data
    html = fetch_ugg("aatrox", "top")
    ssr = extract_json_from_html(html, "window.__SSR_DATA__")

    # Official Riot champion data
    champ_data = get_ssr_subdata(ssr, "en_US/champion.json")
    # SEO aliases (nicknames etc)
    seo_block = get_ssr_subdata(ssr, "seo-champion-names.json")

    alias_map = {}

    for champ_info in champ_data.values():
        canonical = champ_info.get("name")
        slug = champ_info.get("id").lower()
        if not canonical:
            continue

        aliases = {canonical}

        seo_info = seo_block.get(champ_info["key"])
        if seo_info:
            for k in ("name", "altName", "altName2"):
                alt = seo_info.get(k)
                if alt:
                    aliases.add(alt)

        alias_map[canonical] = {
            "slug": slug,
            "name": canonical,
            "aliases": sorted(aliases)
        }

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(alias_map, f, ensure_ascii=False, indent=2)
    with open(version_path, "w") as f:
        f.write(current_version)

    return alias_map



def get_champ_name_variations(user_input: str, alias_map: dict[str, dict]) -> dict:
    """
    Resolves user input to canonical champion data (slug + aliases).
    Returns the full alias_map entry.
    """
    norm_input = normalise(user_input)

    # Exact match through aliases
    for canonical, data in alias_map.items():
        for alias in data["aliases"]:
            if normalise(alias) == norm_input:
                return data  # contains slug & aliases

    # Fuzzy match against aliases
    all_aliases = {
        normalise(alias): canonical
        for canonical, data in alias_map.items()
        for alias in data["aliases"]
    }

    guesses = difflib.get_close_matches(norm_input, all_aliases.keys(), n=1, cutoff=0.5)
    if guesses:
        canonical = all_aliases[guesses[0]]
        return alias_map[canonical]

    raise ValueError(f"Champion '{user_input}' not recognized")

