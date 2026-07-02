$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$env:FLASK_DEBUG = "1"
$env:HOST = "127.0.0.1"
$env:PORT = "5000"
.\.venv\Scripts\python.exe app1.py
