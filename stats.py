import math
import os
from collections import Counter, defaultdict


TYPE_LABELS = {
    "heavyTank": "HT",
    "mediumTank": "MT",
    "lightTank": "LT",
    "AT-SPG": "TD",
}


def make_player_store():
    return {
        "nickname": "unknown",
        "battles": 0,
        "damage": 0,
        "frags": 0,
        "shots": 0,
        "hits": 0,
        "pens": 0,
        "assist": 0,
        "blocked": 0,
        "enemies_damaged": 0,
        "iPoints": 0,
        "sPoints": 0,
        "tank_battles": Counter(),
        "type_battles": Counter(),
    }


def calc_stats(acc_id, player, tank_db):
    battles = player["battles"]
    if battles == 0:
        return None

    adr = player["damage"] / battles
    kpr = player["frags"] / battles
    enemies_damaged = player["enemies_damaged"] / battles
    assist = player["assist"] / battles
    blocked = player["blocked"] / battles
    acc_h = player["hits"] / player["shots"] if player["shots"] else 0
    acc_p = player["pens"] / player["hits"] if player["hits"] else 0
    ipoints = player["iPoints"] / battles
    spoints = player["sPoints"] / battles

    firepower = ((100 + adr) * (1 + kpr) ** (1 / 7) - 777) / 20
    aim = ((1 + acc_h) * (1 + acc_p) - 0.9) / 0.029
    support = ((1 + enemies_damaged) ** 2 * (200 + assist) ** 2 * (400 + blocked)) ** (1 / 3) / 19
    supremacy = math.sqrt(max(0, 40 + ipoints + spoints)) / 0.13
    bpr = (1 / 76) * ((17 * firepower + 3 * aim + 2 * support + 3 * supremacy) / 25)

    main_tank = "unknown"
    if player["tank_battles"]:
        top_id = player["tank_battles"].most_common(1)[0][0]
        main_tank = tank_db.get(top_id, {}).get("name", "unknown")

    return {
        "account_id": acc_id,
        "nickname": player["nickname"],
        "battles": battles,
        "HT": player["type_battles"].get("HT", 0),
        "MT": player["type_battles"].get("MT", 0),
        "LT": player["type_battles"].get("LT", 0),
        "TD": player["type_battles"].get("TD", 0),
        "main_tank": main_tank,
        "ADR": round(adr, 2),
        "frags": player["frags"],
        "KPR": round(kpr, 2),
        "DE": round(enemies_damaged, 2),
        "assist": round(assist, 2),
        "blocked": round(blocked, 2),
        "shots": player["shots"],
        "hits": player["hits"],
        "pens": player["pens"],
        "AccH": round(acc_h * 100, 2),
        "AccP": round(acc_p * 100, 2),
        "iPoints": round(ipoints, 2),
        "sPoints": round(spoints, 2),
        "Firepower": round(firepower, 2),
        "AIM": round(aim, 2),
        "Support": round(support, 2),
        "Supremacy": round(supremacy, 2),
        "BPR": round(bpr, 2),
    }


def bpr_adr_sort(rows):
    return sorted(rows, key=lambda row: (-row["BPR"], -row["ADR"]))


def process_replay_folder(folder_path, parser, tank_db):
    our_players = defaultdict(make_player_store)
    enemy_players = defaultdict(make_player_store)
    errors = []
    processed = 0
    discovered = 0

    for file_name in sorted(os.listdir(folder_path)):
        if not file_name.endswith(".wotbreplay"):
            continue

        discovered += 1
        full_path = os.path.join(folder_path, file_name)
        data, error = parser.battle_results(full_path)
        if error:
            errors.append({"file": file_name, "reason": error})
            continue

        processed += 1
        author_id = data.get("author", {}).get("account_id")
        our_team = None
        player_info_map = {}

        for player in data.get("players", []):
            acc_id = player.get("account_id")
            info = player.get("info", {})
            if not acc_id:
                continue
            player_info_map[acc_id] = {
                "nickname": info.get("nickname", "unknown"),
                "team": info.get("team"),
            }
            if acc_id == author_id:
                our_team = info.get("team")

        if our_team is None:
            errors.append({"file": file_name, "reason": "author team not found"})
            continue

        our_ids = {acc_id for acc_id, info in player_info_map.items() if info["team"] == our_team}
        enemy_ids = {acc_id for acc_id, info in player_info_map.items() if info["team"] != our_team}

        for player in data.get("player_results", []):
            info = player.get("info", {})
            acc_id = info.get("account_id")
            if not acc_id:
                continue

            if acc_id in our_ids:
                store = our_players
            elif acc_id in enemy_ids:
                store = enemy_players
            else:
                continue

            aggregate_player(store[acc_id], acc_id, info, player_info_map, tank_db)

    our_rows = bpr_adr_sort(
        row for acc_id, player in our_players.items() if (row := calc_stats(acc_id, player, tank_db))
    )
    enemy_rows = bpr_adr_sort(
        row for acc_id, player in enemy_players.items() if (row := calc_stats(acc_id, player, tank_db))
    )

    return {
        "our_team": our_rows,
        "enemy_team": enemy_rows,
        "processed": processed,
        "discovered": discovered,
        "errors": errors,
    }


def aggregate_player(player, acc_id, info, player_info_map, tank_db):
    if acc_id in player_info_map:
        player["nickname"] = player_info_map[acc_id]["nickname"]

    player["battles"] += 1
    player["damage"] += info.get("damage_dealt", 0)
    player["frags"] += info.get("n_enemies_destroyed", 0)
    player["shots"] += info.get("n_shots", 0)
    player["hits"] += info.get("n_hits_dealt", 0)
    player["pens"] += info.get("n_penetrations_dealt", 0)
    player["assist"] += info.get("damage_assisted_1", 0) + info.get("damage_assisted_2", 0)
    player["blocked"] += info.get("damage_blocked", 0)
    player["enemies_damaged"] += info.get("n_enemies_damaged", 0)

    earned = info.get("victory_points_earned", 0)
    captured = info.get("victory_points_seized", 0)
    player["iPoints"] += earned - captured
    player["sPoints"] += captured

    tank_id = info.get("tank_id")
    if tank_id:
        player["tank_battles"][tank_id] += 1
        wg_type = tank_db.get(tank_id, {}).get("type", "unknown")
        label = TYPE_LABELS.get(wg_type)
        if label:
            player["type_battles"][label] += 1
