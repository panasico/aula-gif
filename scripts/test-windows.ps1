$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$exePath = Join-Path $repoRoot 'dist\AulaGif.exe'
if (-not (Test-Path -LiteralPath $exePath)) { throw 'Build Windows first' }
$testDir = Join-Path $repoRoot ('dist\test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testDir | Out-Null
Add-Type -AssemblyName System.Drawing
$bitmap = New-Object System.Drawing.Bitmap 240,135
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.Clear([System.Drawing.Color]::Red)
    $bitmap.Save((Join-Path $testDir 'red.gif'), [System.Drawing.Imaging.ImageFormat]::Gif)
} finally { $graphics.Dispose(); $bitmap.Dispose() }
& $exePath convert "$testDir\red.gif" "$testDir\output"
if ($LASTEXITCODE -ne 0) { throw 'Conversion failed' }
$data = [IO.File]::ReadAllBytes("$testDir\output\animation.aula-rgb565")
if ($data[0] -ne 1 -or $data[256] -ne 0 -or $data[257] -ne 248 -or $data.Length -ne 65536) { throw 'RGB565/size check failed' }
& $exePath check "$testDir\output\animation.aula-rgb565"
if ($LASTEXITCODE -ne 0) { throw 'Valid fixture rejected' }
$data[0] = 142
[IO.File]::WriteAllBytes("$testDir\invalid.aula-rgb565", $data)
& $exePath check "$testDir\invalid.aula-rgb565"
if ($LASTEXITCODE -ne 1) { throw 'Invalid frame count accepted' }
Write-Output 'PASS: Windows conversion, byte order, page size, and oversized frame count rejection'
exit 0
