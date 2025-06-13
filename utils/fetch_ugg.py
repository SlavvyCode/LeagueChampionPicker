import os, time, hashlib, requests

from utils.patch import get_effective_patch, HEADERS

CACHE_DIR = "./cache"
CACHE_PERIOD = 60 * 60 * 24 * 3  # 3 days
def fetch_champ_counter_ugg(
        champ: str,
        role: str | None = None,
        add_patch: bool = True,
        use_cache: bool = False
) -> str:
    """
    champ      – champion slug, e.g. 'aatrox'
    role       – lane/position slug; if None the param is omitted
    add_patch  – include ?patch=x_y in URL
    use_cache  – read/write html cache
    """
    os.makedirs(CACHE_DIR, exist_ok=True)

    # build cache-key
    patch_tag = get_effective_patch().replace(".", "_").rsplit("_", 1)[0] if add_patch else None
    role_tag  = role or "norole"
    key  = f"{patch_tag}_{champ.lower()}_{role_tag}"
    path = os.path.join(CACHE_DIR, f"{key}.html")

    if use_cache and os.path.exists(path) and (time.time() - os.path.getmtime(path)) < CACHE_PERIOD:
        return open(path, encoding="utf-8").read()

    # --- build URL ----------------------------------------------------------
    base = f"https://u.gg/lol/champions/{champ}/counter"
    params = []
    if role:
        params.append(f"role={role}")
    if add_patch:
        params.append(f"patch={patch_tag}")
    url = base + ("?" + "&".join(params) if params else "")
    # ----------------------------------------------------------------------

    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()

    with open(path, "w", encoding="utf-8") as f:
        f.write(r.text)
    return r.text