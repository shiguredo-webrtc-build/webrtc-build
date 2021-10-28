$ErrorActionPreference = 'Stop'

$SCRIPT_DIR = (Resolve-Path ".").Path

Push-Location $SCRIPT_DIR
  python3 run.py build windows
  python3 run.py package windows
Pop-Location
