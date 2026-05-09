param(
  [Parameter(Mandatory = $true)]
  [string]$Owner,

  [string]$Repo = "6ure-App",

  [Parameter(Mandatory = $true)]
  [string]$Version,

  [Parameter(Mandatory = $true)]
  [string]$PackagePath,

  [string]$Notes = "",

  [string]$PackageType = "installer",

  [string]$InstallerArgs = "/S",

  [string]$OutputPath = "latest.json"
)

$ErrorActionPreference = "Stop"

$resolvedPackage = Resolve-Path -LiteralPath $PackagePath
$packageName = Split-Path -Leaf $resolvedPackage
$tag = if ($Version.StartsWith("v")) { $Version } else { "v$Version" }
$downloadUrl = "https://github.com/$Owner/$Repo/releases/download/$tag/$packageName"
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedPackage).Hash.ToLowerInvariant()
$size = (Get-Item -LiteralPath $resolvedPackage).Length

$windows = [ordered]@{
  url = $downloadUrl
  sha256 = $hash
  sizeBytes = $size
  packageType = $PackageType
}

if ($PackageType -eq "installer") {
  $windows.installerArgs = $InstallerArgs
  $windows.successExitCodes = @(0, 3010)
}

$manifest = [ordered]@{
  version = $Version.TrimStart("v")
  notes = $Notes
  windows = $windows
}

$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8

Write-Host "Manifest written: $OutputPath"
Write-Host "Package URL: $downloadUrl"
Write-Host "SHA256: $hash"
Write-Host "Size bytes: $size"
