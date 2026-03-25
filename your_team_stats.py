import os
import json
import math
import subprocess
from collections import defaultdict, Counter
from openpyxl import Workbook
from dotenv import load_dotenv

load_dotenv()

REPLAY_FOLDER = os.getenv("REPLAY_FOLDER")
OUTPUT_FILE = os.path.join(REPLAY_FOLDER, "results.xlsx")
TANK_DB_FILE = "tank_db.json"

if not os.path.exists(TANK_DB_FILE):
    print("❌ tank_db.json not found. Run fetch_tanks.py first.")
    exit(1)

with open(TANK_DB_FILE, encoding="utf-8") as f:
    raw_db = json.load(f)
    TANK_DB = {int(k): v for k, v in raw_db.items()}

TYPE_LABELS = {
    "heavyTank":  "HT",
    "mediumTank": "MT",
    "lightTank":  "LT",
    "AT-SPG":     "TD",
}

def run_parser(file_path):
    result = subprocess.run(
        ["wotbreplay-inspector", "battle-results", file_path],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print("❌ Error:", file_path)
        return None
    return json.loads(result.stdout)

players = defaultdict(lambda: {
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
})

for file in os.listdir(REPLAY_FOLDER):
    if not file.endswith(".wotbreplay"):
        continue

    full_path = os.path.join(REPLAY_FOLDER, file)
    data = run_parser(full_path)
    if not data:
        continue

    # --- find our team number from author ---
    author_id = data.get("author", {}).get("account_id")
    our_team = None

    # build player info map: account_id -> {nickname, team}
    player_info_map = {}
    for p in data.get("players", []):
        acc_id = p.get("account_id")
        info = p.get("info", {})
        if acc_id:
            player_info_map[acc_id] = {
                "nickname": info.get("nickname", "unknown"),
                "team": info.get("team"),
            }
            if acc_id == author_id:
                our_team = info.get("team")

    if our_team is None:
        print(f"⚠️  Could not determine our team in {file}, skipping.")
        continue

    # set of account_ids on our team (from players[])
    our_team_ids = {
        acc_id for acc_id, info in player_info_map.items()
        if info["team"] == our_team
    }

    # player_results only has players who actually played (no spectators)
    # additionally filter to our team only
    for p in data.get("player_results", []):
        info = p.get("info", {})
        acc_id = info.get("account_id")

        if not acc_id:
            continue

        # skip if not on our team
        if acc_id not in our_team_ids:
            continue

        pl = players[acc_id]

        if acc_id in player_info_map:
            pl["nickname"] = player_info_map[acc_id]["nickname"]

        pl["battles"] += 1
        pl["damage"]          += info.get("damage_dealt", 0)
        pl["frags"]           += info.get("n_enemies_destroyed", 0)
        pl["shots"]           += info.get("n_shots", 0)
        pl["hits"]            += info.get("n_hits_dealt", 0)
        pl["pens"]            += info.get("n_penetrations_dealt", 0)
        pl["assist"]          += info.get("damage_assisted_1", 0) + info.get("damage_assisted_2", 0)
        pl["blocked"]         += info.get("damage_blocked", 0)
        pl["enemies_damaged"] += info.get("n_enemies_damaged", 0)

        earned   = info.get("victory_points_earned", 0)
        captured = info.get("victory_points_seized", 0)
        pl["iPoints"] += (earned - captured)
        pl["sPoints"] += captured

        tank_id = info.get("tank_id")
        if tank_id:
            pl["tank_battles"][tank_id] += 1
            tank_info = TANK_DB.get(tank_id, {})
            wg_type = tank_info.get("type", "unknown")
            label = TYPE_LABELS.get(wg_type)
            if label:
                pl["type_battles"][label] += 1

# --- calculations ---
rows = []

for acc_id, p in players.items():
    b = p["battles"]
    if b == 0:
        continue

    ADR     = p["damage"] / b
    KPR     = p["frags"] / b
    DE      = p["enemies_damaged"] / b
    Assist  = p["assist"] / b
    Blocked = p["blocked"] / b

    AccH = p["hits"] / p["shots"] if p["shots"] else 0
    AccP = p["pens"] / p["hits"]  if p["hits"]  else 0

    iPoints = p["iPoints"] / b
    sPoints = p["sPoints"] / b

    Firepower  = ((100 + ADR) * (1 + KPR) ** (1/7) - 777) / 20
    AIM        = ((1 + AccH) * (1 + AccP) - 0.9) / 0.029
    Support    = ((1 + DE)**2 * (200 + Assist)**2 * (400 + Blocked)) ** (1/3) / 19
    Supremacy  = math.sqrt(40 + iPoints + sPoints) / 0.13
    BPR        = (1/76) * ((17*Firepower + 3*AIM + 2*Support + 3*Supremacy) / 25)

    if p["tank_battles"]:
        top_tank_id = p["tank_battles"].most_common(1)[0][0]
        main_tank = TANK_DB.get(top_tank_id, {}).get("name", "unknown")
    else:
        main_tank = "unknown"

    HT = p["type_battles"].get("HT", 0)
    MT = p["type_battles"].get("MT", 0)
    LT = p["type_battles"].get("LT", 0)
    TD = p["type_battles"].get("TD", 0)

    rows.append([
        acc_id,
        p["nickname"],
        b,
        HT, MT, LT, TD,
        main_tank,
        round(ADR, 2),
        p["frags"],
        round(KPR, 2),
        round(DE, 2),
        round(Assist, 2),
        round(Blocked, 2),
        p["shots"],
        p["hits"],
        p["pens"],
        round(AccH * 100, 2),
        round(AccP * 100, 2),
        round(iPoints, 2),
        round(sPoints, 2),
        round(Firepower, 2),
        round(AIM, 2),
        round(Support, 2),
        round(Supremacy, 2),
        round(BPR, 2)
    ])

rows.sort(key=lambda x: x[-1], reverse=True)

# --- Excel ---
wb = Workbook()
ws = wb.active
ws.title = "Stats"

ws.append([
    "account_id", "nickname", "battles",
    "HT", "MT", "LT", "TD", "main_tank",
    "ADR", "Frags", "KPR", "DE", "Assist", "Blocked",
    "shots", "hits", "pens",
    "AccH (%)", "AccP (%)",
    "iPoints", "sPoints",
    "Firepower", "AIM", "Support", "Supremacy", "BPR 2.0"
])

for row in rows:
    ws.append(row)

wb.save(OUTPUT_FILE)
print("✅ DONE! Excel saved as:", OUTPUT_FILE)