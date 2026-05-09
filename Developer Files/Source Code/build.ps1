$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$appName = "6ure$([char]0x2122) App"

$version = $env:REYLI_APP_VERSION
if (-not $version) {
  $version = $env:APP_VERSION
}
if (-not $version) {
  $serverText = Get-Content -Raw -LiteralPath ".\server.py"
  $match = [regex]::Match($serverText, 'DEFAULT_APP_VERSION\s*=\s*"([^"]+)"')
  if ($match.Success) {
    $version = $match.Groups[1].Value
  }
}
if (-not $version) {
  throw "App version was not set."
}
$version = $version.Trim().TrimStart("v")
$versionPayload = [ordered]@{ version = $version }
$versionPayload | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $root "app-version.json") -Encoding UTF8
Write-Host "App version: $version"

python -m PyInstaller --noconfirm --clean ".\6ure Files.spec"

if ($LASTEXITCODE -ne 0) {
  throw "$appName build failed with exit code $LASTEXITCODE"
}

$distDir = Join-Path $root "dist\$appName"
$updateConfig = Join-Path $root "update-config.json"
if (Test-Path -LiteralPath $updateConfig) {
  Copy-Item -LiteralPath $updateConfig -Destination (Join-Path $distDir "update-config.json") -Force
}
$presenceConfig = Join-Path $root "discord-presence.json"
if (Test-Path -LiteralPath $presenceConfig) {
  Copy-Item -LiteralPath $presenceConfig -Destination (Join-Path $distDir "discord-presence.json") -Force
}
Write-Host "Built: $distDir\$appName.exe"
