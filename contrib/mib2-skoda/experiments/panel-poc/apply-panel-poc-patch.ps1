# Opt-in ChairPlay updateDisplayPanels POC. Applies only after the existing profile+scaling fixes.
# No upstream source vendored; exact pinned upstream and all unique context anchors are enforced.
param([Parameter(Mandatory=$true)][string]$Checkout)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$root = (Resolve-Path -LiteralPath $Checkout).Path
$manifestPath = Join-Path $project 'patches\panel-poc\manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$revision = (& git -C $root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $revision -ne $manifest.upstreamRevision) {
  throw "Unexpected upstream revision $revision (expected $($manifest.upstreamRevision))"
}

$pending = [System.Collections.ArrayList]::new()
$utf8 = [System.Text.UTF8Encoding]::new($false)
foreach ($entry in $manifest.edits) {
  $relative = [string]$entry.path
  if ([string]::IsNullOrWhiteSpace($relative) -or $relative.Contains('..') -or $relative.StartsWith('/')) {
    throw "Unsafe source path $relative"
  }
  $file = Join-Path $root $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing upstream source: $relative" }
  if ($null -ne $entry.sha -and $entry.sha -ne '') {
    $hash = (& git -C $root hash-object -- $file).Trim()
    if ($LASTEXITCODE -ne 0 -or $hash -ne $entry.sha) {
      throw "Source drift ${relative}: blob $hash != $($entry.sha)"
    }
  }
  $content = [System.IO.File]::ReadAllText($file).Replace([string][char]13 + [string][char]10, [string][char]10)
  foreach ($step in $entry.steps) {
    $before = [string]$step.before
    $after = [string]$step.after
    $first = $content.IndexOf($before, [StringComparison]::Ordinal)
    $last = $content.LastIndexOf($before, [StringComparison]::Ordinal)
    if ($first -lt 0 -or $first -ne $last -or $before.Length -lt 10) {
      throw "Panel patch anchor not unique in $relative (first=$first last=$last)"
    }
    $content = $content.Substring(0, $first) + $after + $content.Substring($first + $before.Length)
  }
  [void]$pending.Add(@{ Path = $file; Text = $content; Name = $relative })
}
foreach ($copy in $manifest.copies) {
  $relative = [string]$copy.target
  $sourceName = [string]$copy.source
  if ($relative.Contains('..') -or $sourceName.Contains('..') -or
      $relative.StartsWith('/') -or $sourceName.StartsWith('/')) { throw 'Unsafe copy path' }
  $source = Join-Path $project $sourceName.Replace('/', [IO.Path]::DirectorySeparatorChar)
  $target = Join-Path $root $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing new source $sourceName" }
  if (Test-Path -LiteralPath $target) { throw "POC source already exists: $relative" }
  $content = [System.IO.File]::ReadAllText($source).Replace([string][char]13 + [string][char]10, [string][char]10)
  [void]$pending.Add(@{ Path = $target; Text = $content; Name = $relative })
}

# Only write after all guards have passed: fail closed before any partial patch.
foreach ($item in $pending) {
  $parent = Split-Path -Parent $item.Path
  [System.IO.Directory]::CreateDirectory($parent) | Out-Null
  [System.IO.File]::WriteAllText($item.Path, $item.Text, $utf8)
  Write-Host "PANEL_POC_PATCH_OK $($item.Name)"
}
Write-Host "PANEL_POC_PATCH=PASS files=$($pending.Count)"
