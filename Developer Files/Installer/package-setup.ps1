param(
  [string]$Version = "",
  [string]$OutputDir = "Setup Output",
  [switch]$KeepStaging
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspace = Resolve-Path (Join-Path $scriptDir "..\..")
$sourceCodeDir = Join-Path $workspace "Developer Files\Source Code"
$applicationDir = Join-Path $workspace "Application"
$outputRoot = Join-Path $workspace $OutputDir
$stageRoot = Join-Path $outputRoot "staging"
$appName = "6ure$([char]0x2122) App"
$legacyAppName = "6ure Files"
$exeName = "$appName.exe"
$stageAppDir = Join-Path $stageRoot $appName
$iconPath = Join-Path $sourceCodeDir "assets\6ure-logo.ico"

if (-not (Test-Path -LiteralPath $applicationDir)) {
  throw "Application folder was not found: $applicationDir"
}

if (-not $Version) {
  $serverPath = Join-Path $sourceCodeDir "server.py"
  $serverText = Get-Content -Raw -LiteralPath $serverPath
  $match = [regex]::Match($serverText, 'APP_VERSION\s*=\s*os\.environ\.get\("REYLI_APP_VERSION",\s*"([^"]+)"\)')
  if (-not $match.Success) {
    throw "Could not read APP_VERSION from server.py"
  }
  $Version = $match.Groups[1].Value
}

$safeVersion = $Version -replace '[^0-9A-Za-z._-]', '-'
$versionParts = @($Version -split '[^0-9]+' | Where-Object { $_ -ne "" } | Select-Object -First 4)
while ($versionParts.Count -lt 4) {
  $versionParts += "0"
}
$nsisProductVersion = ($versionParts | ForEach-Object {
  $part = [int]$_
  if ($part -gt 65535) { "65535" } else { [string]$part }
}) -join "."
$zipPath = Join-Path $outputRoot "6ure-app-files-$safeVersion.zip"
$setupPath = Join-Path $outputRoot "6ure-app-setup-$safeVersion.exe"
$nsiPath = Join-Path $outputRoot "6ure-app-setup-$safeVersion.nsi"

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
if (Test-Path -LiteralPath $stageRoot) {
  Remove-Item -LiteralPath $stageRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stageAppDir | Out-Null

Get-ChildItem -LiteralPath $applicationDir -Force | Copy-Item -Destination $stageAppDir -Recurse -Force

foreach ($required in @($exeName, "_internal", "update-config.json")) {
  if (-not (Test-Path -LiteralPath (Join-Path $stageAppDir $required))) {
    throw "Required application file is missing: $required"
  }
}

$blocked = Get-ChildItem -LiteralPath $stageRoot -Recurse -Force | Where-Object {
  $_.FullName -match '\\Developer Files(\\|$)'
}
if ($blocked) {
  throw "Developer Files leaked into setup staging."
}

if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
Start-Sleep -Seconds 1
Compress-Archive -LiteralPath $stageAppDir -DestinationPath $zipPath -Force

$nsis = @"
Unicode true
Name "$appName"
OutFile "$setupPath"
InstallDir "`$LOCALAPPDATA\Programs\$appName"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "$nsisProductVersion"
VIAddVersionKey "ProductName" "$appName"
VIAddVersionKey "CompanyName" "reyli"
VIAddVersionKey "FileDescription" "$appName Setup"
VIAddVersionKey "FileVersion" "$Version"
VIAddVersionKey "ProductVersion" "$Version"
VIAddVersionKey "LegalCopyright" "reyli"

!include MUI2.nsh
!define MUI_ABORTWARNING
!define MUI_ICON "$iconPath"
!define MUI_UNICON "$iconPath"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "`$INSTDIR"
  File /r "$stageAppDir\*"
  WriteUninstaller "`$INSTDIR\Uninstall.exe"
  Delete "`$DESKTOP\$legacyAppName.lnk"
  Delete "`$SMPROGRAMS\$legacyAppName\$legacyAppName.lnk"
  RMDir "`$SMPROGRAMS\$legacyAppName"
  CreateDirectory "`$SMPROGRAMS\$appName"
  CreateShortcut "`$SMPROGRAMS\$appName\$appName.lnk" "`$INSTDIR\$exeName"
  CreateShortcut "`$DESKTOP\$appName.lnk" "`$INSTDIR\$exeName"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$legacyAppName"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "DisplayName" "$appName"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "DisplayVersion" "$Version"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "Publisher" "reyli"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "InstallLocation" "`$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "UninstallString" '"`$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "`$DESKTOP\$appName.lnk"
  Delete "`$DESKTOP\$legacyAppName.lnk"
  Delete "`$SMPROGRAMS\$appName\$appName.lnk"
  Delete "`$SMPROGRAMS\$legacyAppName\$legacyAppName.lnk"
  RMDir "`$SMPROGRAMS\$appName"
  RMDir "`$SMPROGRAMS\$legacyAppName"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$legacyAppName"
  RMDir /r "`$INSTDIR"
SectionEnd
"@

Set-Content -LiteralPath $nsiPath -Value $nsis -Encoding UTF8

$makensisCandidates = @(
  "C:\Program Files (x86)\NSIS\makensis.exe",
  "C:\Program Files\NSIS\makensis.exe"
)
$makensis = $makensisCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $makensis) {
  $command = Get-Command makensis.exe -ErrorAction SilentlyContinue
  if ($command) {
    $makensis = $command.Source
  }
}
if (-not $makensis) {
  throw "NSIS makensis.exe was not found. Install NSIS or compile $nsiPath manually."
}

& $makensis $nsiPath
if ($LASTEXITCODE -ne 0) {
  throw "NSIS setup build failed with exit code $LASTEXITCODE"
}

$zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
$setupHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $setupPath).Hash.ToLowerInvariant()

if (-not $KeepStaging -and (Test-Path -LiteralPath $stageRoot)) {
  Remove-Item -LiteralPath $stageRoot -Recurse -Force
}

Write-Host "App files ZIP: $zipPath"
Write-Host "Setup EXE: $setupPath"
Write-Host "NSIS script: $nsiPath"
Write-Host "ZIP SHA256: $zipHash"
Write-Host "Setup SHA256: $setupHash"
