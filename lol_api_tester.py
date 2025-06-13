import argparse, pathlib, sys
import base64

import urllib3
from riotwatcher import LolWatcher, RiotWatcher, ApiError
import requests
import json



def get_local_champ_select():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Path to the lockfile
    lockfile_path = 'D:/Games/Riot Games/League of Legends/lockfile'

    # Read and parse the lockfile
    with open(lockfile_path, 'r') as f:
        content = f.read().split(':')
        port = content[2]
        password = content[3]

    # Construct the authorization header
    auth_token = base64.b64encode(f'riot:{password}'.encode()).decode()
    headers = {
        'Authorization': f'Basic {auth_token}'
    }

    # Construct the URL using the dynamic port
    url = f'https://127.0.0.1:{port}/lol-champ-select/v1/session'

    # Make the GET request
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch data: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")


def champ_id_to_name(champ_id):
    # Get the champion data
    champions = lol_watcher.data_dragon.champions('13.19.1')
    # Find the champion name by ID
    for champ in champions['data'].values():
        if int(champ['key']) == champ_id:
            return champ['name']
    return None


ign = "Slavvy"  # Summoner name (before the '#')
tag_line = "SLAV"  # Region tag (e.g., EUW, NA1, etc.)
my_region = 'euw1'
api_key = open('riot_api_key.env').read().strip()
lol_watcher = LolWatcher(api_key)
riot_watcher = RiotWatcher(api_key)


def api_shenanigans():
    account_info = riot_watcher.account.by_riot_id("europe", ign, tag_line)

    puuid = account_info['puuid']
    assert puuid != None


def get_champs_in_teams_in_local_champ_select():
    champ_select_info = get_local_champ_select()
    # for each team
    latest_version = lol_watcher.data_dragon.versions_for_region(my_region)['n']['champion']
    champion_data = requests.get(
        f'https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/champion.json'
    ).json()['data']
    champ_id_to_name = {int(info['key']): name for name, info in champion_data.items()}


    # champs already cached in champ_id_to_name
    my_team_ids    = [p['championId'] for p in champ_select_info.get('myTeam', [])]
    their_team_ids = [p['championId'] for p in champ_select_info.get('theirTeam', [])]

    # ignore empty (0 = not locked yet)
    my_team_names    = [champ_id_to_name.get(cid) for cid in my_team_ids if cid]
    their_team_names = [champ_id_to_name.get(cid) for cid in their_team_ids if cid]

    # print("Ally: ", my_team_names)
    # print("Enemy:", their_team_names)

    returndict = {
        'allyChamps': my_team_names,
        'enemyChamps': their_team_names
    }
    return returndict


def get_roles_playrate(champ_ugg, role):

    # comapre rolematches for each world emerald plus role
    # "rankings_emerald_plus_world::https://stats2.u.gg/lol/1.5/rankings/15_9/ranked_solo_5x5/83/1.5.0.json": {
    #     "data": {
    #         "world_emerald_plus_jungle": {
    #             ...,...,
    #             "roleMatches": 4157,
    """
    Return % of games this champion is played in the given role
    (emerald-plus, world).

    champ_ugg : JSON block for one champion from U.GG stats API
    role      : 'top' | 'jungle' | 'mid' | 'bot' | 'support'

    Returns a float in [0,1]. 0 if data missing.
    """
    role = role.lower()
    bucket = f"world_emerald_plus_{role}"

    # collect counts for all five roles
    roles = ("top", "jungle", "mid", "adc", "support")
    counts = []
    for r in roles:
        b = f"world_emerald_plus_{r}"
        counts.append(champ_ugg["data"].get(b, {}).get("roleMatches", 0))

    total = sum(counts)
    if total == 0:
        return 0.0

    return champ_ugg["data"].get(bucket, {}).get("roleMatches", 0) / total


# foreach champ in my_team_champs:
# fetch ugg data for champ
# get role playrate for each role for champ
# tell the user which champion is most likely to be played in which role
# return dict with likeliest role:champ pairings
# todo?
def estimate_enemy_team_roles():
    return
    # enemyTeam = get_champs_in_teams_in_local_champ_select().enemyChamps



#
#
# def blindpick_helper_based_on_enemy_teamcomp
#     # most useful when 2nd to last pick.
#     # get the enemy team comp and go through heuristics
#     #
#
#
#     # todo can i find these heuristics somewhere
#     # example
#     # if enemy has a lot of frontliners - braum sup, jarvan jg, galio mid, you will be super useful
#     # if enemy a lot of CC - pick olaf
#     # if enemy has NO CC, pick irelia
#     # if enemy has a lot of AA champs - pick jax or Malphite
#     # if enemy has a lot of beefy champs - pick gwen
#     # if enemy has a lot of no max hp building champs - pick mundo
#     # if enemy has a lot of dashes - pick poppy
#
#
# # more examples - sett countered by range
# # morde - likes against enchanters
# # garen - mostly universal
# # yorick - dislikes oneshotters on side
# # yone likes champs without disengage
# # teemo - likes against melee
# # malphite 0 likes all AD comps
# # rene - likes strong earlygame team on his team
# # sion dislikes antitanks
# # ksante - universal
# # jayce - broken blindpick
# # nasus - bad into strong earlygame junglers
# # kayle - hates a good enemy jungler
# # volibear - likes heavy engagers on his team and earlygame jungler
# # riven - loves no CC enemy
# # urgot hates high range
# # gp-  likes immobile ADC
# # gnar - op  blindpick - loves melees enemy though
#

if __name__ == "__main__":
    enemy_champs = get_champs_in_teams_in_local_champ_select().enemyChamps
#     print enemy champs+ assign each a number 1 to 5
    for i, champ in enumerate(enemy_champs, start=1):
        print(f"{i}. {champ}")
#  ask user to pick a number of who they think is the enemy laner
    print("Pick a number for the enemy laner:")
    try:
        choice = int(input())
        if 1 <= choice <= len(enemy_champs):
            enemy_laner = enemy_champs[choice - 1]
        else:
            print("Invalid choice. Please pick a number from the list.")
    except ValueError:
        print("Invalid input. Please enter a number.")




