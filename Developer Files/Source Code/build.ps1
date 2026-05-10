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

$versionParts = @($version -split '[^0-9]+' | Where-Object { $_ -ne "" } | Select-Object -First 4)
while ($versionParts.Count -lt 4) {
  $versionParts += "0"
}
$versionParts = $versionParts | ForEach-Object {
  $part = [int]$_
  if ($part -gt 65535) { "65535" } else { [string]$part }
}
$fileVersionTuple = $versionParts -join ", "
$fileVersionText = $versionParts -join "."
$versionInfo = @"
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($fileVersionTuple),
    prodvers=($fileVersionTuple),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'reyli'),
          StringStruct('FileDescription', '6ure App desktop client'),
          StringStruct('FileVersion', '$fileVersionText'),
          StringStruct('InternalName', '6ure App'),
          StringStruct('OriginalFilename', '6ure App.exe'),
          StringStruct('ProductName', '6ure App'),
          StringStruct('ProductVersion', '$fileVersionText'),
          StringStruct('LegalCopyright', 'Copyright reyli')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@
$versionInfo | Set-Content -LiteralPath (Join-Path $root "version_info.txt") -Encoding UTF8

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

function Get-CodeSigningCertificate {
  param([string]$Thumbprint)
  $cleanThumbprint = ($Thumbprint -replace '\s', '').ToUpperInvariant()
  if (-not $cleanThumbprint) {
    return $null
  }
  foreach ($storePath in @("Cert:\CurrentUser\My", "Cert:\LocalMachine\My")) {
    $cert = Get-ChildItem -Path $storePath -CodeSigningCert -ErrorAction SilentlyContinue |
      Where-Object { ($_.Thumbprint -replace '\s', '').ToUpperInvariant() -eq $cleanThumbprint } |
      Select-Object -First 1
    if ($cert) {
      return $cert
    }
  }
  return $null
}

function Sign-BuildFileIfConfigured {
  param([string]$Path)
  $thumbprint = $env:REYLI_CODE_SIGN_THUMBPRINT
  if (-not $thumbprint) {
    return
  }
  $cert = Get-CodeSigningCertificate -Thumbprint $thumbprint
  if (-not $cert) {
    throw "Code signing certificate was not found for REYLI_CODE_SIGN_THUMBPRINT."
  }
  $timestampUrl = $env:REYLI_CODE_SIGN_TIMESTAMP_URL
  if (-not $timestampUrl) {
    $timestampUrl = "http://timestamp.digicert.com"
  }
  $signature = Set-AuthenticodeSignature -LiteralPath $Path -Certificate $cert -TimestampServer $timestampUrl
  if ($signature.Status -ne "Valid") {
    throw "Code signing failed for ${Path}: $($signature.StatusMessage)"
  }
}

$exePath = Join-Path $distDir "$appName.exe"
Sign-BuildFileIfConfigured -Path $exePath
Write-Host "Built: $distDir\$appName.exe"
