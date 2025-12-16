# start.ps1 - start Tools Hub via launcher (no .bat needed)
$ErrorActionPreference = "Stop"

# Force UTF-8 in this console (avoids weird characters)
try { chcp 65001 | Out-Null } catch {}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# Prefer venv python if present, otherwise use system python
$VenvPy = Join-Path $Root "venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
  & $VenvPy "launcher\launcher.py"
  exit $LASTEXITCODE
}

# If no venv yet, use system python to run launcher (launcher will create venv)
$Py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py) {
  Write-Host "Python not found in PATH. Install Python 3.11+ first." -ForegroundColor Red
  exit 1
}

& $Py "launcher\launcher.py"
exit $LASTEXITCODE
