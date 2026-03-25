# WoT Blitz Replay Analyzer

A Python tool that parses World of Tanks Blitz replay files and generates an Excel spreadsheet with per-player performance statistics and BPR 2.0 ratings for your team.

---

## Dependencies

### wotbreplay-inspector

This project relies on [wotbreplay-inspector](https://github.com/eigenein/wotbreplay-inspector) — a third-party CLI tool by **eigenein** for extracting battle results from `.wotbreplay` files.

Install it before running this project:

```bash
pip install wotbreplay-inspector
```

> **Note:** `wotbreplay-inspector` is not part of this repository. All credit for replay parsing goes to its author. Please refer to its [repository](https://github.com/eigenein/wotbreplay-inspector) for documentation and support.

---

## Requirements

- Python 3.9+
- A Wargaming API application ID — register one free at [developers.wargaming.net](https://developers.wargaming.net/) 
**ONLY FOR UPDATE TANK DATABASE IN APPLICATION**

### Python packages

```bash
pip install wotbreplay-inspector python-dotenv requests openpyxl
```
---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/roklimovich/wotblitz-replay-analyzer.git
cd your-repo
```

### 2. Install dependencies

```bash
pip install wotbreplay-inspector python-dotenv requests openpyxl
```

### 3. Configure environment

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
WG_APP_ID=your_application_id_here
WG_REGION=com
REPLAY_FOLDER=D:\World of Tanks Blitz\replays\your_folder
```

| Variable        | Description                                              |
|-----------------|----------------------------------------------------------|
| `WG_APP_ID`     | Your Wargaming API application ID                        |
| `WG_REGION`     | Server region: `com`, `eu`, `ru`, or `asia`              |
| `REPLAY_FOLDER` | Full path to the folder containing your `.wotbreplay` files |

> ⚠️ `.env` is listed in `.gitignore` and will never be committed.

### 4. Fetch the tank database

Run once to download tank names and types from the WG API:

```bash
python fetch_tanks.py
```

This creates `tank_db.json` locally. Re-run it whenever new tanks are added to the game.

### 5. Run the main script

```bash
python main.py
```

The output file `results.xlsx` will be saved inside your `REPLAY_FOLDER`.

---

## Output

The spreadsheet contains one row per player on **your team only**, sorted by BPR 2.0 descending.

| Column       | Description                                      |
|--------------|--------------------------------------------------|
| `account_id` | WG account ID                                    |
| `nickname`   | Player nickname                                  |
| `battles`    | Number of battles in the replay set              |
| `HT`         | Battles played on Heavy Tanks                    |
| `MT`         | Battles played on Medium Tanks                   |
| `LT`         | Battles played on Light Tanks                    |
| `TD`         | Battles played on Tank Destroyers                |
| `main_tank`  | Most played tank                                 |
| `ADR`        | Average damage per battle                        |
| `Frags`      | Total kills                                      |
| `KPR`        | Kills per battle                                 |
| `DE`         | Average enemies damaged per battle               |
| `Assist`     | Average assist damage per battle                 |
| `Blocked`    | Average blocked damage per battle                |
| `shots`      | Total shots fired                                |
| `hits`       | Total hits dealt                                 |
| `pens`       | Total penetrations dealt                         |
| `AccH (%)`   | Hit accuracy percentage                          |
| `AccP (%)`   | Penetration accuracy percentage                  |
| `iPoints`    | Average supremacy points earned (capture)        |
| `sPoints`    | Average supremacy points seized                  |
| `Firepower`  | Calibrated firepower rating                      |
| `AIM`        | Calibrated aim rating                            |
| `Support`    | Calibrated support rating                        |
| `Supremacy`  | Calibrated supremacy rating                      |
| `BPR 2.0`    | Overall performance rating                       |

### BPR 2.0 Formula

```
Firepower  = [(100 + ADR) × (1 + KPR)^(1/7) − 777] / 20
AIM        = [(1 + AccH)(1 + AccP) − 0.9] / 0.029
Support    = [(1 + DE)² × (200 + Assist)² × (400 + Blocked)]^(1/3) / 19
Supremacy  = √(40 + iPoints + sPoints) / 0.13

BPR 2.0    = (1/76) × [(17×Firepower + 3×AIM + 2×Support + 3×Supremacy) / 25]
```

---

## Notes

- Only players on **your team** are included. Team is determined automatically from the replay author field.
```
your_team_stats.py
```
- If a tank ID is not found in `tank_db.json`, the `main_tank` column shows `unknown` and that battle does not count toward type totals. Re-running `fetch_tanks.py` usually fixes this.

