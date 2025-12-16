# trust_cert.ps1 - add localhost cert to CurrentUser Trusted Root (no admin needed)
$ErrorActionPreference = "Stop"
try { chcp 65001 | Out-Null } catch {}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Root  # scripts/ -> repo root

$Branding = Join-Path $Root "config\branding.json"
$crtName = "localhost.crt"
try {
  $b = Get-Content $Branding -Raw | ConvertFrom-Json
  if ($b.cert.cert_filename) { $crtName = $b.cert.cert_filename }
} catch {}

$CertPath = Join-Path $Root ("certs\" + $crtName)
if (-not (Test-Path $CertPath)) {
  Write-Host "Cert not found: $CertPath" -ForegroundColor Red
  exit 1
}

Write-Host "Importing cert into CurrentUser\Root (Trusted Root)..."
# certutil usually works without admin when using -user
certutil -user -addstore Root $CertPath | Out-Host

Write-Host "Done. Close ALL browsers and re-open Edge/Chrome."
