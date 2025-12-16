# stop.ps1 - best-effort stop (kills run.py launched from this repo)
$ErrorActionPreference = "SilentlyContinue"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Root   # scripts/ -> repo root

# Try: kill python processes where command line contains this repo + run.py
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | ForEach-Object {
  $cmd = $_.CommandLine
  if ($cmd -and $cmd.ToLower().Contains($Root.ToLower()) -and $cmd.ToLower().Contains("run.py")) {
    Write-Host ("Stopping PID {0}: {1}" -f $_.ProcessId, $cmd)
    Stop-Process -Id $_.ProcessId -Force
  }
}

# Also try to stop launcher itself
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | ForEach-Object {
  $cmd = $_.CommandLine
  if ($cmd -and $cmd.ToLower().Contains($Root.ToLower()) -and $cmd.ToLower().Contains("launcher.py")) {
    Write-Host ("Stopping launcher PID {0}" -f $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force
  }
}
