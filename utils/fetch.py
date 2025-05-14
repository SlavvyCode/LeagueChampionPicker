import os, time, hashlib, requests

from utils.patch import get_effective_patch, HEADERS

CACHE_DIR = "./cache"
CACHE_PERIOD = 60 * 60 * 24 * 3  # 3 days

def  fetch_ugg(champ: str, role: str, use_cache=False) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    patch = get_effective_patch()
    key = f"{patch}_{champ.lower()}_{role.lower()}"
    path = os.path.join(CACHE_DIR, f"{key}.html")

    if use_cache and os.path.exists(path) and (time.time() - os.path.getmtime(path)) < CACHE_PERIOD:
        return open(path, "r", encoding="utf-8").read()

    patch = get_effective_patch()
    ## is in format 15.9.1
    patch = patch.replace(".", "_")
    # remove the last digit
    patch = patch.rsplit("_", 1)[0]

    url = f"https://u.gg/lol/champions/{champ}/counter?role={role}&patch={patch}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    html = r.text

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return html
