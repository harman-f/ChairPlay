# Apply audited unified-diff hunks to the pinned ChairPlay checkout after the live URL patch.
# Uses exact text/context replacements because two source files are already modified in-memory
# by the prior SHA-guarded patch. Validate all files before writing any of them.
param(
  [Parameter(Mandatory=$true)][string]$Checkout,
  [Parameter(Mandatory=$true)][string]$PatchPath
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $Checkout).Path
$revision = (& git -C $root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $revision -ne 'fd7a22fa1f503695309ec9efad0e48b2d900349f') {
  throw "Unexpected ChairPlay revision $revision; refusing Scaling patch"
}
$patch = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $PatchPath).Path).Replace("`r`n", "`n")
$blocks = [regex]::Split($patch, '(?m)(?=^diff --git a/)') | Where-Object { $_.StartsWith('diff --git a/') }
if ($blocks.Count -ne 7) { throw "Expected 7 source files in Scaling patch, found $($blocks.Count)" }
$pending = @()
$contextComparison = [StringComparison]::Ordinal
foreach ($block in $blocks) {
  $head = [regex]::Match($block, '^diff --git a/(.+?) b/(.+?)\n')
  if (-not $head.Success -or $head.Groups[1].Value -ne $head.Groups[2].Value) { throw 'Invalid Scaling patch file header' }
  $name = $head.Groups[1].Value
  if ($name.Contains('..') -or $name.StartsWith('/')) { throw "Unsafe patch path $name" }
  $file = Join-Path $root $name.Replace('/', [IO.Path]::DirectorySeparatorChar)
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing source $name" }
  $source = [System.IO.File]::ReadAllText($file).Replace("`r`n", "`n")
  $inHunk = $false
  $before = [System.Collections.Generic.List[string]]::new()
  $after = [System.Collections.Generic.List[string]]::new()
  $hunks = 0
  foreach ($line in ($block -split "`n")) {
    if ($line.StartsWith('@@ ')) {
      if ($inHunk) {
        $needle = $before -join "`n"
        $replace = $after -join "`n"
        $first = $source.IndexOf($needle, $contextComparison)
        if ($first -lt 0 -or $first -ne $source.LastIndexOf($needle, $contextComparison)) {
          throw "Scaling patch mismatch $name hunk $hunks first=$first chars=$($needle.Length)"
        }
        $source = $source.Replace($needle, $replace)
      }
      $inHunk = $true
      $hunks += 1
      $before.Clear()
      $after.Clear()
      continue
    }
    if (-not $inHunk -or $line.Length -eq 0) { continue }
    if ($line.StartsWith('\\ No newline at end of file')) { continue }
    $marker = $line.Substring(0,1)
    $value = $line.Substring(1)
    switch ($marker) {
      ' ' { $before.Add($value); $after.Add($value) }
      '-' { $before.Add($value) }
      '+' { $after.Add($value) }
      default { throw "Unsupported patch line in $name hunk $hunks" }
    }
  }
  if ($inHunk) {
    $needle = $before -join "`n"
    $replace = $after -join "`n"
    $first = $source.IndexOf($needle, $contextComparison)
    if ($first -lt 0 -or $first -ne $source.LastIndexOf($needle, $contextComparison)) {
      throw "Scaling patch mismatch $name hunk $hunks first=$first chars=$($needle.Length)"
    }
    $source = $source.Replace($needle, $replace)
  }
  if ($hunks -eq 0) { throw "No hunks in $name" }
  $pending += @{ File = $file; Text = $source; Name = $name; Hunks = $hunks }
}
foreach ($entry in $pending) {
  [System.IO.File]::WriteAllText($entry.File, $entry.Text, [System.Text.UTF8Encoding]::new($false))
  Write-Host "MANUAL_SCALING_PATCH_OK $($entry.Name) hunks=$($entry.Hunks)"
}
Write-Host "MANUAL_SCALING_PATCH=PASS files=$($pending.Count)"
