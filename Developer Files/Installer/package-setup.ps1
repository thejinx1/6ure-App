param(
  [string]$Version = "",
  [string]$SourceAppDir = "",
  [string]$OutputDir = "Setup Output",
  [string]$CodeSignThumbprint = $env:REYLI_CODE_SIGN_THUMBPRINT,
  [string]$TimestampUrl = $env:REYLI_CODE_SIGN_TIMESTAMP_URL,
  [switch]$KeepStaging
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspace = Resolve-Path (Join-Path $scriptDir "..\..")
$sourceCodeDir = Join-Path $workspace "Developer Files\Source Code"
$applicationDir = Join-Path $workspace "Application"
$distAppDir = Join-Path $sourceCodeDir "dist\6ure$([char]0x2122) App"
$outputRoot = Join-Path $workspace $OutputDir
$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) "6ure-setup-staging-$PID"
$appName = "6ure$([char]0x2122) App"
$legacyAppName = "6ure Files"
$exeName = "$appName.exe"
$legacyExeName = "$legacyAppName.exe"
$stageAppDir = Join-Path $stageRoot "app-files"
$zipAppDir = Join-Path $stageRoot $appName
$iconPath = Join-Path $sourceCodeDir "assets\6ure-logo.ico"
if (-not $TimestampUrl) {
  $TimestampUrl = "http://timestamp.digicert.com"
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

function Sign-InstallerFileIfConfigured {
  param([string]$Path)
  if (-not $CodeSignThumbprint) {
    return
  }
  $cert = Get-CodeSigningCertificate -Thumbprint $CodeSignThumbprint
  if (-not $cert) {
    throw "Code signing certificate was not found for the configured thumbprint."
  }
  $signature = Set-AuthenticodeSignature -LiteralPath $Path -Certificate $cert -TimestampServer $TimestampUrl
  if ($signature.Status -ne "Valid") {
    throw "Code signing failed for ${Path}: $($signature.StatusMessage)"
  }
}

function Write-Utf8BomFile {
  param(
    [string]$Path,
    [string]$Value
  )
  $utf8Bom = New-Object System.Text.UTF8Encoding $true
  [System.IO.File]::WriteAllText($Path, $Value, $utf8Bom)
}

if (-not $SourceAppDir) {
  if (Test-Path -LiteralPath $distAppDir) {
    $SourceAppDir = $distAppDir
  } else {
    $SourceAppDir = $applicationDir
  }
}
$resolvedSourceAppDir = (Resolve-Path -LiteralPath $SourceAppDir).Path
if (-not (Test-Path -LiteralPath $resolvedSourceAppDir)) {
  throw "Source application folder was not found: $resolvedSourceAppDir"
}

if (-not $Version) {
  $versionCandidates = @(
    (Join-Path $sourceCodeDir "app-version.json")
  )
  foreach ($candidate in $versionCandidates) {
    if ($Version -or -not (Test-Path -LiteralPath $candidate)) {
      continue
    }
    try {
      $payload = Get-Content -Raw -LiteralPath $candidate | ConvertFrom-Json
      $Version = [string]$payload.version
    } catch {}
  }
  if (-not $Version) {
    $serverPath = Join-Path $sourceCodeDir "server.py"
    $serverText = Get-Content -Raw -LiteralPath $serverPath
    $match = [regex]::Match($serverText, 'DEFAULT_APP_VERSION\s*=\s*"([^"]+)"')
    if (-not $match.Success) {
      throw "Could not read DEFAULT_APP_VERSION from server.py"
    }
    $Version = $match.Groups[1].Value
  }
}
$Version = $Version.Trim().TrimStart("v")

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

Get-ChildItem -LiteralPath $resolvedSourceAppDir -Force | Copy-Item -Destination $stageAppDir -Recurse -Force
Get-ChildItem -LiteralPath $stageAppDir -Recurse -Force -Filter "*.lnk" | Remove-Item -Force
Get-ChildItem -LiteralPath $stageAppDir -Recurse -Force | Where-Object {
  $_.Name -in @(
    "6ure-files-state.json",
    "6ure-files-state.backup.json",
    "6ure-files-state.tmp",
    "app-settings.json",
    "last-repair.json",
    "leaker-proxy-cookies.lwp",
    "6ure-secure-vault.json",
    "6ure-secure-vault.key",
    "hlx-api-key.txt",
    "hlx-api-key.db",
    "app-version.json",
    "discord-presence.json",
    "update-config.json"
  )
} | Remove-Item -Force

foreach ($required in @($exeName, "$appName.pkg")) {
  if (-not (Test-Path -LiteralPath (Join-Path $stageAppDir $required))) {
    throw "Required application file is missing: $required"
  }
}

foreach ($hiddenRuntimeItem in @("_internal", "app-version.json", "discord-presence.json", "update-config.json")) {
  if (Test-Path -LiteralPath (Join-Path $stageAppDir $hiddenRuntimeItem)) {
    throw "Runtime item should be embedded in the package, not visible in setup staging: $hiddenRuntimeItem"
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
New-Item -ItemType Directory -Force -Path $zipAppDir | Out-Null
Get-ChildItem -LiteralPath $stageAppDir -Force | Copy-Item -Destination $zipAppDir -Recurse -Force
Start-Sleep -Seconds 1
Compress-Archive -LiteralPath $zipAppDir -DestinationPath $zipPath -Force

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
!define MUI_FINISHPAGE_RUN "`$INSTDIR\$exeName"
!define MUI_FINISHPAGE_RUN_TEXT "Launch $appName"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  SetShellVarContext current
FunctionEnd

Function un.onInit
  SetShellVarContext current
FunctionEnd

Function CloseRunningApp
  DetailPrint "Closing running $appName windows..."
  nsExec::ExecToStack 'taskkill /IM "$exeName" /T /F'
  Pop `$0
  Pop `$1
  nsExec::ExecToStack 'taskkill /IM "$legacyExeName" /T /F'
  Pop `$0
  Pop `$1
  Sleep 1800
FunctionEnd

Section "$appName" SEC_APP
  SectionIn RO
  Call CloseRunningApp
  SetOutPath "`$INSTDIR"
  RMDir /r "`$INSTDIR\_internal"
  Delete "`$INSTDIR\app-version.json"
  Delete "`$INSTDIR\discord-presence.json"
  Delete "`$INSTDIR\update-config.json"
  Delete "`$INSTDIR\hlx-api-key.txt"
  Delete "`$INSTDIR\hlx-api-key.db"
  File /r "$stageAppDir\*"
  WriteUninstaller "`$INSTDIR\Uninstall.exe"
  Delete "`$DESKTOP\$appName.lnk"
  Delete "`$DESKTOP\$legacyAppName.lnk"
  Delete "`$SMPROGRAMS\$legacyAppName\$legacyAppName.lnk"
  RMDir "`$SMPROGRAMS\$legacyAppName"
  CreateDirectory "`$SMPROGRAMS\$appName"
  CreateShortcut "`$SMPROGRAMS\$appName\$appName.lnk" "`$INSTDIR\$exeName"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$legacyAppName"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "DisplayName" "$appName"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "DisplayVersion" "$Version"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "Publisher" "reyli"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "InstallLocation" "`$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "UninstallString" '"`$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" "NoRepair" 1
SectionEnd

Section "Create desktop shortcut" SEC_DESKTOP
  SetOutPath "`$INSTDIR"
  CreateShortcut "`$DESKTOP\$appName.lnk" "`$INSTDIR\$exeName"
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

Write-Utf8BomFile -Path $nsiPath -Value $nsis

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

Sign-InstallerFileIfConfigured -Path $setupPath

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
