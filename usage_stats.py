import json
import os
import tempfile
from pathlib import Path


DEFAULT_STATS = {
    "sessions": 0,
    "replays": 0,
    "players": 0,
}


class UsageStats:
    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        if not self.path.exists():
            return DEFAULT_STATS.copy()
        try:
            with self.path.open(encoding="utf-8") as stats_file:
                stored = json.load(stats_file)
        except (OSError, json.JSONDecodeError):
            return DEFAULT_STATS.copy()

        stats = DEFAULT_STATS.copy()
        for key in stats:
            stats[key] = int(stored.get(key, 0) or 0)
        return stats

    def add_session(self, result):
        replays = int(result.get("processed", 0) or 0)
        players = len(result.get("our_team", [])) + len(result.get("enemy_team", []))
        if replays <= 0 and players <= 0:
            return self.read()

        stats = self.read()
        stats["sessions"] += 1
        stats["replays"] += replays
        stats["players"] += players
        self._write_atomic(stats)
        return stats

    def _write_atomic(self, stats):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="usage_stats_", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                json.dump(stats, temp_file, indent=2)
            os.replace(temp_path, self.path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
