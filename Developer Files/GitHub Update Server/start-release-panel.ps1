$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath ".panel-venv")) {
    python -m venv .panel-venv
}

.\.panel-venv\Scripts\python.exe -m pip install --upgrade pip
.\.panel-venv\Scripts\python.exe -m pip install -r requirements-release-panel.txt
.\.panel-venv\Scripts\python.exe release-panel.py
