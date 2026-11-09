# Build-time only: apply exact, reviewed UI consolidation replacements to the pinned transient ChairPlay checkout.
# This is NOT a user installation script and is never included in the patch ZIP.
param(
  [Parameter(Mandatory=$true)][string]$Checkout,
  [Parameter(Mandatory=$true)][string]$PatchPath
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $Checkout).Path
$revision = (& git -C $root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $revision -ne 'fd7a22fa1f503695309ec9efad0e48b2d900349f') {
  throw "Wrong ChairPlay upstream commit $revision"
}
$patch = Get-Content -LiteralPath (Resolve-Path -LiteralPath $PatchPath).Path -Raw | ConvertFrom-Json
if ($patch.upstreamRevision -ne $revision -or $patch.operations.Count -lt 10) {
  throw "Invalid consolidation patch manifest"
}
$files = @{}
foreach ($step in $patch.operations) {
  $name = [string]$step.path
  if ($name.Contains('..') -or $name.StartsWith('/') -or !$name.StartsWith('webui/src/pages/')) {
    throw "Unsafe patch path: $name"
  }
  $filename = Join-Path $root ($name.Replace('/', [IO.Path]::DirectorySeparatorChar))
  if (!$files.ContainsKey($name)) {
    if (!(Test-Path -LiteralPath $filename -PathType Leaf)) { throw "Missing target: $name" }
    $files[$name] = [IO.File]::ReadAllText($filename).Replace("`r`n", "`n")
  }
  $source = [string]$files[$name]
  $before = [string]$step.before
  $after = [string]$step.after
  if (!$before) { throw "Empty matching text for $name" }
  $first = $source.IndexOf($before, [StringComparison]::Ordinal)
  $last = $source.LastIndexOf($before, [StringComparison]::Ordinal)
  if ($first -lt 0 -or $first -ne $last) {
    throw "UI patch drift: $name, first=$first last=$last, beforeLength=$($before.Length)"
  }
  $files[$name] = $source.Replace($before, $after)
}
foreach ($name in $files.Keys) {
  $filename = Join-Path $root ($name.Replace('/', [IO.Path]::DirectorySeparatorChar))
  [IO.File]::WriteAllText($filename, [string]$files[$name], [Text.UTF8Encoding]::new($false))
  Write-Host "UI_CONSOLIDATION_V2_OK $name"
}
Write-Host "UI_CONSOLIDATION_V2=PASS files=$($files.Count) operations=$($patch.operations.Count)"
