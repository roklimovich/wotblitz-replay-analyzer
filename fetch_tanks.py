import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("WG_APP_ID")
REGION = os.getenv("WG_REGION", "com")  # com | eu | ru | asia

BASE_URL = f"https://api.wotblitz.{REGION}/wotb/encyclopedia/vehicles/"
FALLBACK_URL = "https://raw.githubusercontent.com/Jylpah/blitz-tools/master/tanks.json"


def load_from_wargaming():
    vehicles = {}
    page_no = 1

    while True:
        response = requests.get(
            BASE_URL,
            params={
                "application_id": APP_ID,
                "fields": "tank_id,name,type",
                "page_no": page_no,
                "limit": 100,
            },
            timeout=30,
        )
        data = response.json()

        if data.get("status") != "ok":
            raise RuntimeError(f"Wargaming API error: {data}")

        vehicles.update(data.get("data", {}))
        meta = data.get("meta", {})
        if page_no >= meta.get("page_total", 1):
            break
        page_no += 1

    return normalize_tanks(vehicles)


def load_from_fallback():
    response = requests.get(FALLBACK_URL, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return normalize_tanks(payload.get("data", payload))


def normalize_tanks(vehicles):
    return {
        int(tank_id): {
            "name": info.get("name", "unknown"),
            "type": info.get("type", "unknown"),
        }
        for tank_id, info in vehicles.items()
    }


if APP_ID:
    tank_db = load_from_wargaming()
    source = "Wargaming API"
else:
    print("WG_APP_ID is not set; using public fallback tank list.")
    tank_db = load_from_fallback()
    source = "fallback tank list"

with open("tank_db.json", "w", encoding="utf-8") as file:
    json.dump(dict(sorted(tank_db.items())), file, ensure_ascii=False, indent=2)

print(f"Saved {len(tank_db)} tanks to tank_db.json from {source}.")
