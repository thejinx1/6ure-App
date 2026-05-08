param(
  [string]$Version = "",
  [string]$BaseUrl = "",
  [string]$OutputDir = "releases",
  [string]$Notes = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$appName = "6ure$([char]0x2122) App"

if (-not $Version) {
  $serverText = Get-Content -Raw -Path ".\server.py"
  $match = [regex]::Match($serverText, 'APP_VERSION\s*=\s*os\.environ\.get\("REYLI_APP_VERSION",\s*"([^"]+)"\)')
  if (-not $match.Success) {
    throw "Could not read APP_VERSION from server.py"
  }
  $Version = $match.Groups[1].Value
}

powershell -ExecutionPolicy Bypass -File ".\build.ps1"
if ($LASTEXITCODE -ne 0) {
  throw "Build failed with exit code $LASTEXITCODE"
}

$distDir = Join-Path $root "dist\$appName"
$releaseDir = Join-Path $root $OutputDir
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null

$zipName = "6ure-app-$Version-win64.zip"
$zipPath = Join-Path $releaseDir $zipName
if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path (Join-Path $distDir "*") -DestinationPath $zipPath -Force
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
$size = (Get-Item -LiteralPath $zipPath).Length
$packageUrl = if ($BaseUrl) { "$($BaseUrl.TrimEnd('/'))/$zipName" } else { "https://example.com/updates/$zipName" }

$manifest = [ordered]@{
  version = $Version
  notes = $Notes
  windows = [ordered]@{
    url = $packageUrl
    sha256 = $hash
    sizeBytes = $size
    packageType = "zip"
  }
}

$manifestPath = Join-Path $releaseDir "latest.json"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath -Encoding UTF8

Write-Host "Release package: $zipPath"
Write-Host "Manifest: $manifestPath"
Write-Host "SHA256: $hash"
