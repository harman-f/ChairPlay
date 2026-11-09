# Build-time-only exact source patcher for ChairPlay Fast Smart Update v3.
# The user-facing patch ZIP contains only changed installed files, never this helper.
param(
  [Parameter(Mandatory=$true)][string]$Checkout,
  [Parameter(Mandatory=$true)][string]$PatchPath
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $Checkout).Path
$revision = (& git -C $root rev-parse HEAD).Trim()
$expected = 'fd7a22fa1f503695309ec9efad0e48b2d900349f'
if ($LASTEXITCODE -ne 0 -or $revision -ne $expected) {
  throw "Unexpected ChairPlay upstream $revision"
}
$submodule = (& git -C (Join-Path $root 'upstream') rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $submodule -ne '28d6002ba00320f0ba745212160b08759e4f60b9') {
  throw "Unexpected DiPlay upstream $submodule"
}
$patch = Get-Content -LiteralPath (Resolve-Path -LiteralPath $PatchPath).Path -Raw | ConvertFrom-Json
if ($patch.upstreamRevision -ne $revision -or $patch.operations.Count -lt 20) {
  throw "Invalid Fast Smart Update manifest"
}
$allowedPrefixes = @(
  'webui/src/',
  'src/main/kotlin/io/github/numberonebot/chairplay/',
  'src/test/kotlin/io/github/numberonebot/chairplay/',
  'upstream/shared/src/main/java/com/shilapi/xcertplay/airplay/'
)
$files = @{}
foreach ($step in $patch.operations) {
  $name = [string]$step.path
  $allowed = $false
  foreach ($prefix in $allowedPrefixes) { if ($name.StartsWith($prefix, [StringComparison]::Ordinal)) { $allowed = $true; break } }
  if (!$allowed -or $name.Contains('..') -or $name.Contains('\') -or $name.StartsWith('/')) {
    throw "Unsafe source path $name"
  }
  $filename = Join-Path $root $name.Replace('/', [IO.Path]::DirectorySeparatorChar)
  if (!$files.ContainsKey($name)) {
    if (!(Test-Path -LiteralPath $filename -PathType Leaf)) { throw "Missing target $name" }
    $files[$name] = [IO.File]::ReadAllText($filename).Replace("`r`n", "`n")
  }
  $source = [string]$files[$name]
  $before = [string]$step.before
  $after = [string]$step.after
  if (!$before) { throw "Empty match text in $name" }
  $first = $source.IndexOf($before, [StringComparison]::Ordinal)
  $last = $source.LastIndexOf($before, [StringComparison]::Ordinal)
  if ($first -lt 0 -or $first -ne $last) {
    throw "Fast Smart Update drift $name first=$first last=$last bytes=$($before.Length)"
  }
  $files[$name] = $source.Replace($before, $after)
}
foreach ($name in $files.Keys) {
  $filename = Join-Path $root $name.Replace('/', [IO.Path]::DirectorySeparatorChar)
  [IO.File]::WriteAllText($filename, [string]$files[$name], [Text.UTF8Encoding]::new($false))
  Write-Host "FAST_SMART_PATCH_OK $name"
}
Write-Host "FAST_SMART_PATCH=PASS files=$($files.Count) operations=$($patch.operations.Count)"
