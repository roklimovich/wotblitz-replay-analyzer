import json
import os
import secrets
import shutil
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from excel_export import send_stats_workbook
from excel_import import parse_team_database
from replay_parser import ReplayParser
from stats import process_replay_folder
from usage_stats import UsageStats


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TANK_DB_FILE = BASE_DIR / "tank_db.json"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "512"))
MAX_UPLOAD_FILES = int(os.getenv("MAX_UPLOAD_FILES", "200"))
MAX_TEMP_UPLOAD_DIRS = int(os.getenv("MAX_TEMP_UPLOAD_DIRS", "20"))
UPLOAD_TTL_SECONDS = int(os.getenv("UPLOAD_TTL_SECONDS", "1800"))
UPLOAD_TMP_ROOT = Path(os.getenv("UPLOAD_TMP_ROOT", tempfile.gettempdir())) / "blitzscrim_uploads"
USAGE_STATS_FILE = Path(os.getenv("USAGE_STATS_FILE", BASE_DIR / "data" / "usage_stats.json"))
SHARED_REPORTS_DIR = Path(os.getenv("SHARED_REPORTS_DIR", BASE_DIR / "data" / "shared_reports"))
SHARE_TTL_SECONDS = int(os.getenv("SHARE_TTL_SECONDS", "86400"))
PUBLIC_MODE = os.getenv("PUBLIC_MODE", "0") == "1"

app = Flask(__name__, static_folder="static")
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

parser = ReplayParser(os.getenv("WOTBREPLAY_INSPECTOR_BIN", "wotbreplay-inspector"))
usage_stats = UsageStats(USAGE_STATS_FILE)
tank_db = {}

if TANK_DB_FILE.exists():
    with TANK_DB_FILE.open(encoding="utf-8") as tank_file:
        tank_db = {int(key): value for key, value in json.load(tank_file).items()}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/analyze")
def analyze():
    return send_from_directory("static", "index.html")


@app.route("/s/<share_id>")
def shared_report_page(share_id):
    return send_from_directory("static", "index.html")


@app.route("/privacy")
def privacy():
    return send_from_directory("static", "privacy.html")


@app.route("/api/health")
def health():
    cleanup_shared_reports()
    parser_path = parser.path()
    checks = {
        "parser": bool(parser_path),
        "tank_db": bool(tank_db),
    }
    return jsonify({
        "ok": all(checks.values()),
        "checks": checks,
        "parser": parser_path,
        "tank_count": len(tank_db),
        "max_upload_mb": MAX_UPLOAD_MB,
        "max_upload_files": MAX_UPLOAD_FILES,
        "max_temp_upload_dirs": MAX_TEMP_UPLOAD_DIRS,
        "upload_ttl_seconds": UPLOAD_TTL_SECONDS,
        "share_ttl_seconds": SHARE_TTL_SECONDS,
        "public_mode": PUBLIC_MODE,
    })


@app.route("/api/public-stats")
def public_stats():
    return jsonify(usage_stats.read())


@app.route("/api/process", methods=["POST"])
def process():
    if PUBLIC_MODE:
        return jsonify({"error": "Folder paths are disabled in public mode. Upload replay files instead."}), 403
    if not parser.available():
        return parser_missing_response()

    data = request.json or {}
    folder = data.get("folder", "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "Invalid folder path"}), 400

    result = process_replay_folder(folder, parser, tank_db)
    usage_stats.add_session(result)
    return jsonify(result)


@app.route("/api/upload", methods=["POST"])
def upload():
    if not parser.available():
        return parser_missing_response()

    cleanup_upload_storage()
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400
    if len(files) > MAX_UPLOAD_FILES:
        return jsonify({"error": f"Too many files. Maximum is {MAX_UPLOAD_FILES} replays per upload."}), 413
    invalid_files = [file.filename for file in files if not is_replay_file(file.filename)]
    if invalid_files:
        return jsonify({"error": "Only .wotbreplay files are accepted."}), 400

    UPLOAD_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix="session_", dir=UPLOAD_TMP_ROOT)
    try:
        saved = save_replay_uploads(files, tmp_dir)
        if saved == 0:
            return jsonify({"error": "No .wotbreplay files found in upload"}), 400
        result = process_replay_folder(tmp_dir, parser, tank_db)
        usage_stats.add_session(result)
        return jsonify(result)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.route("/api/session/close", methods=["POST"])
def close_session():
    cleanup_upload_storage()
    return ("", 204)


@app.route("/api/export", methods=["POST"])
def export():
    data = request.json or {}
    return send_stats_workbook(data.get("our_team", []), data.get("enemy_team", []))


@app.route("/api/team-db/import", methods=["POST"])
def import_team_db():
    uploaded_file = request.files.get("file")
    if not uploaded_file:
        return jsonify({"error": "No Excel file uploaded"}), 400
    if not uploaded_file.filename.lower().endswith(".xlsx"):
        return jsonify({"error": "Only .xlsx files are accepted."}), 400

    try:
        players = parse_team_database(uploaded_file)
    except Exception as exc:
        return jsonify({"error": f"Cannot read Excel file: {exc}"}), 400

    if not players:
        return jsonify({"error": "No players found. The file must include a nickname/player column."}), 400
    return jsonify({"players": players, "count": len(players)})


@app.route("/api/share", methods=["POST"])
def create_share():
    cleanup_shared_reports()
    data = request.json or {}
    if not data.get("our_team") and not data.get("enemy_team"):
        return jsonify({"error": "No report loaded to share"}), 400

    share_id = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12]
    now = int(time.time())
    payload = {
        "id": share_id,
        "created_at": now,
        "expires_at": now + SHARE_TTL_SECONDS,
        "report": {
            "our_team": data.get("our_team", []),
            "enemy_team": data.get("enemy_team", []),
            "processed": int(data.get("processed") or 0),
            "discovered": int(data.get("discovered") or data.get("processed") or 0),
            "errors": data.get("errors", []),
            "mode": data.get("mode") or "scrim",
            "uploads": int(data.get("uploads") or 1),
        },
    }

    SHARED_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = shared_report_path(share_id)
    tmp_path = report_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload), encoding="utf-8")
    tmp_path.replace(report_path)
    return jsonify({
        "id": share_id,
        "url": request.host_url.rstrip("/") + f"/s/{share_id}",
        "expires_at": payload["expires_at"],
        "ttl_seconds": SHARE_TTL_SECONDS,
    })


@app.route("/api/share/<share_id>")
def get_share(share_id):
    cleanup_shared_reports()
    if not valid_share_id(share_id):
        return jsonify({"error": "Invalid share link"}), 400
    report_path = shared_report_path(share_id)
    if not report_path.exists():
        return jsonify({"error": "Share link expired or not found"}), 404

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if payload.get("expires_at", 0) <= int(time.time()):
        report_path.unlink(missing_ok=True)
        return jsonify({"error": "Share link expired"}), 410
    return jsonify(payload)


def save_replay_uploads(files, target_dir):
    saved = 0
    for uploaded_file in files:
        if not is_replay_file(uploaded_file.filename):
            continue
        file_name = os.path.basename(uploaded_file.filename)
        uploaded_file.save(os.path.join(target_dir, file_name))
        saved += 1
    return saved


def is_replay_file(file_name):
    return file_name.lower().endswith(".wotbreplay")


def parser_missing_response():
    return jsonify({"error": "wotbreplay-inspector is not installed or not in PATH"}), 503


def cleanup_upload_storage(max_age_seconds=UPLOAD_TTL_SECONDS):
    if not UPLOAD_TMP_ROOT.exists():
        return

    now = time.time()
    sessions = []
    for path in UPLOAD_TMP_ROOT.iterdir():
        if not path.is_dir():
            continue
        age = now - path.stat().st_mtime
        sessions.append((path.stat().st_mtime, path))
        if age >= max_age_seconds:
            shutil.rmtree(path, ignore_errors=True)

    remaining = [item for item in sessions if item[1].exists()]
    if len(remaining) <= MAX_TEMP_UPLOAD_DIRS:
        return

    for _, path in sorted(remaining)[:len(remaining) - MAX_TEMP_UPLOAD_DIRS]:
        shutil.rmtree(path, ignore_errors=True)


def valid_share_id(share_id):
    return share_id.isalnum() and 8 <= len(share_id) <= 24


def shared_report_path(share_id):
    return SHARED_REPORTS_DIR / f"{share_id}.json"


def cleanup_shared_reports():
    if not SHARED_REPORTS_DIR.exists():
        return

    now = int(time.time())
    for path in SHARED_REPORTS_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("expires_at", 0) <= now:
                path.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError):
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
