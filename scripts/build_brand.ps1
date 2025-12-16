# build_brand.ps1 - create a branded subset build (skeleton)
# This creates a new folder with selected tools + branding tweaks.
$ErrorActionPreference = "Stop"
try { chcp 65001 | Out-Null } catch {}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Root  # scripts/ -> repo root

$OutDir = Read-Host "Output folder (absolute or relative)"
if ([string]::IsNullOrWhiteSpace($OutDir)) { throw "No output folder given" }
if (-not ([System.IO.Path]::IsPathRooted($OutDir))) { $OutDir = Join-Path $Root $OutDir }

$BrandName = Read-Host "New app name (e.g. IntTools)"
if ([string]::IsNullOrWhiteSpace($BrandName)) { $BrandName = "Tools Hub" }

# Pick tools
$toolsJsonPath = Join-Path $Root "config\tools.json"
$tools = (Get-Content $toolsJsonPath -Raw | ConvertFrom-Json).tools

Write-Host ""
Write-Host "Tools:"
for ($i=0; $i -lt $tools.Count; $i++) {
  Write-Host ("[{0}] {1} ({2})" -f $i, $tools[$i].name, $tools[$i].script)
}
Write-Host ""
$sel = Read-Host "Select tool indexes (comma separated), e.g. 0,2,3"
$idx = $sel.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^\d+$' } | ForEach-Object { [int]$_ }

$selected = @()
foreach ($i in $idx) {
  if ($i -ge 0 -and $i -lt $tools.Count) { $selected += $tools[$i] }
}

if ($selected.Count -eq 0) { throw "No tools selected." }

# Copy whole repo as base
if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
Copy-Item -Path $Root -Destination $OutDir -Recurse -Force

# Replace branding.json
$brandingPath = Join-Path $OutDir "config\branding.json"
$branding = Get-Content $brandingPath -Raw | ConvertFrom-Json
$branding.app_name = $BrandName
$branding.window_title = $BrandName
$branding.header_title = $BrandName
$branding.tray_title = $BrandName
$branding.popup_title = $BrandName
$branding | ConvertTo-Json -Depth 12 | Set-Content -Path $brandingPath -Encoding UTF8

# Reduce tools.json
$newToolsJson = @{ tools = $selected }
$newToolsJson | ConvertTo-Json -Depth 12 | Set-Content -Path (Join-Path $OutDir "config\tools.json") -Encoding UTF8

Write-Host ""
Write-Host "Branded build created at: $OutDir"
Write-Host "Next: run scripts\start.ps1 inside that folder."
