# Windows GitHub Actions can take longer than Vitest's default 5s timeout.
# Change the temporary upstream CHECKOUT'S TEST COMMAND ONLY, never production source.
param([Parameter(Mandatory = $true)][string]$Checkout)
$ErrorActionPreference = 'Stop'
$path = Join-Path (Resolve-Path $Checkout).Path 'gradle/web.gradle.kts'
if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing upstream Gradle test runner: $path" }
$source = [System.IO.File]::ReadAllText($path)
$old = '"run", "--reporter=default", "--reporter=junit"'
$new = '"run", "--testTimeout=15000", "--reporter=default", "--reporter=junit"'
if ($source.Contains($new)) { Write-Host 'TEST_TIMEOUT=15000 already applied'; exit 0 }
if (-not $source.Contains($old)) { throw 'Unexpected upstream Vitest runner; refusing test-harness modification.' }
if ($source.IndexOf($old) -ne $source.LastIndexOf($old)) { throw 'Multiple Vitest runner occurrences; refusing modification.' }
[System.IO.File]::WriteAllText($path, $source.Replace($old, $new), [System.Text.UTF8Encoding]::new($false))
Write-Host 'TEST_TIMEOUT=15000 (Windows runner test command only; no application sources overwritten)'
