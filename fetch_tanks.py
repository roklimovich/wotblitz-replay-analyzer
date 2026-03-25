import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("WG_APP_ID")
REGION = os.getenv("WG_REGION", "com")  # com | eu | ru | asia

BASE_URL = f"https://api.wotblitz.{REGION}/wotb/encyclopedia/vehicles/"

tank_db = {}
page_no = 1

while True:
    resp = requests.get(BASE_URL, params={
        "application_id": APP_ID,
        "fields": "tank_id,name,type",
        "page_no": page_no,
        "limit": 100,
    })
    data = resp.json()

    if data.get("status") != "ok":
        print("API error:", data)
        break

    vehicles = data.get("data", {})
    if not vehicles:
        break

    for tank_id_str, info in vehicles.items():
        tank_db[int(tank_id_str)] = {
            "name": info.get("name", "unknown"),
            "type": info.get("type", "unknown"),  # heavyTank | mediumTank | lightTank | AT-SPG
        }

    # WG encyclopedia endpoint returns all at once (no pagination needed),
    # so break after first successful page
    break

with open("tank_db.json", "w", encoding="utf-8") as f:
    json.dump(tank_db, f, ensure_ascii=False, indent=2)

print(f"✅ Saved {len(tank_db)} tanks to tank_db.json")