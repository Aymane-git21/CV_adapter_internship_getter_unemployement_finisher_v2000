# Portable toolchain setup for the docgen comparison bench.
# User-scope, no admin, no PATH changes: pinned official releases are
# downloaded into <repo>/.tools/ (gitignored). Typst itself is already a
# project prerequisite (winget install Typst.Typst — see the runbook skill).
#
# Pinned versions (bump deliberately, they are part of the benchmark record):
$TectonicVersion = '0.16.9'
$QuartoVersion   = '1.9.38'

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repo  = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$tools = Join-Path $repo '.tools'
$dl    = Join-Path $tools 'dl'
New-Item -ItemType Directory -Force $dl | Out-Null

$tectonicZip = Join-Path $dl "tectonic-$TectonicVersion.zip"
$tectonicDir = Join-Path $tools 'tectonic'
if (-not (Test-Path (Join-Path $tectonicDir 'tectonic.exe'))) {
    $url = "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40$TectonicVersion/tectonic-$TectonicVersion-x86_64-pc-windows-msvc.zip"
    Write-Host "Downloading Tectonic $TectonicVersion (~19 MB) from $url"
    Invoke-WebRequest $url -OutFile $tectonicZip
    Expand-Archive $tectonicZip -DestinationPath $tectonicDir -Force
}

$quartoZip = Join-Path $dl "quarto-$QuartoVersion.zip"
$quartoDir = Join-Path $tools 'quarto'
if (-not (Test-Path (Join-Path $quartoDir 'bin\quarto.exe'))) {
    $url = "https://github.com/quarto-dev/quarto-cli/releases/download/v$QuartoVersion/quarto-$QuartoVersion-win.zip"
    Write-Host "Downloading Quarto $QuartoVersion (~134 MB) from $url"
    Invoke-WebRequest $url -OutFile $quartoZip
    Expand-Archive $quartoZip -DestinationPath $quartoDir -Force
}

& (Join-Path $tectonicDir 'tectonic.exe') --version
& (Join-Path $quartoDir 'bin\quarto.exe') --version
Write-Host 'Toolchains ready under .tools/. First tectonic compile downloads TeX packages (~1 min, cached afterwards).'
