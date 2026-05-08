$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$appName = "6ure$([char]0x2122) App"

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
