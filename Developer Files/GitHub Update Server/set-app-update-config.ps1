param(
  [Parameter(Mandatory = $true)]
  [string]$Owner,

  [string]$Repo = "6ure-files-updates",

  [string]$SourceCodeDir = "..\Source Code",

  [string]$ApplicationDir = "..\..\Application"
)

$ErrorActionPreference = "Stop"

$manifestUrl = "https://$Owner.github.io/$Repo/latest.json"
$config = [ordered]@{
  manifestUrl = $manifestUrl
  channel = "stable"
  allowInsecure = $false
}

$paths = @(
  (Join-Path $SourceCodeDir "update-config.json"),
  (Join-Path $ApplicationDir "update-config.json"),
  (Join-Path $SourceCodeDir "dist\6ure Files\update-config.json")
)

foreach ($path in $paths) {
  $parent = Split-Path -Parent $path
  if (Test-Path -LiteralPath $parent) {
    $config | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $path -Encoding UTF8
    Write-Host "Updated: $path"
  }
}

Write-Host "Manifest URL: $manifestUrl"
