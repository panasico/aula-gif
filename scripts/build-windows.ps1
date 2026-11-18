$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$releaseDir = Join-Path $repoRoot 'dist'
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
$compilerPath = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compilerPath /nologo /target:exe "/out:$releaseDir\AulaGif.exe" /reference:System.Drawing.dll /reference:System.Windows.Forms.dll "$repoRoot\windows\AulaGif.cs"
if ($LASTEXITCODE -ne 0) { throw 'Compilation failed' }
Compress-Archive -Path "$releaseDir\AulaGif.exe", "$repoRoot\README.md", "$repoRoot\LICENSE" -DestinationPath "$releaseDir\aula-gif-0.1.0-windows.zip" -Force
Get-FileHash "$releaseDir\aula-gif-0.1.0-windows.zip" -Algorithm SHA256
