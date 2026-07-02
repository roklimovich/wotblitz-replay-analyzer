import json
import os
import shutil
import subprocess


class ReplayParser:
    def __init__(self, executable="wotbreplay-inspector"):
        self.executable = executable

    def path(self):
        if os.path.basename(self.executable) == self.executable:
            return shutil.which(self.executable)
        return self.executable if os.path.exists(self.executable) else None

    def available(self):
        return self.path() is not None

    def battle_results(self, file_path):
        try:
            result = subprocess.run(
                [self.executable, "battle-results", file_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            return None, "wotbreplay-inspector is not installed or not in PATH"
        except subprocess.TimeoutExpired:
            return None, "parser timeout"

        if result.returncode != 0:
            reason = result.stderr.strip() or "parser failed"
            return None, reason

        try:
            return json.loads(result.stdout), None
        except json.JSONDecodeError:
            return None, "parser returned invalid JSON"
