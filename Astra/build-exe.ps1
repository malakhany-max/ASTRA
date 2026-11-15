param([string]$AstronautName = 'Astronaut', [string]$GroundStationName = 'GroundStation')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Invoke-Native {
    param([string]$FilePath, [string[]]$Arguments, [string]$Failure)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $FilePath @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($code -ne 0) { throw $Failure }
}

$env:VITE_API_BASE = 'http://127.0.0.1:8000'
$env:VITE_GROUND_BASE = 'http://127.0.0.1:8100'
$env:VITE_COMPANION_BASE = 'http://127.0.0.1:8200'
$env:VITE_LINK_BASE = 'http://127.0.0.1:8300'
$env:VITE_LOCAL_PROXY = 'true'
$env:VITE_APP_KIND = 'astronaut'
Invoke-Native 'npm' @('run', 'build', '--workspace', 'web-astronaut') 'Astronaut web build failed.'
$env:VITE_APP_KIND = 'ground'
Invoke-Native 'npm' @('run', 'build', '--workspace', 'web-ground') 'Ground Station web build failed.'
Remove-Item Env:VITE_API_BASE, Env:VITE_GROUND_BASE, Env:VITE_COMPANION_BASE, Env:VITE_LINK_BASE, Env:VITE_LOCAL_PROXY, Env:VITE_APP_KIND -ErrorAction SilentlyContinue

$Python = if (Test-Path '.venv-build/Scripts/python.exe') {
    (Resolve-Path '.venv-build/Scripts/python.exe').Path
} elseif (Test-Path '.venv/Scripts/python.exe') {
    (Resolve-Path '.venv/Scripts/python.exe').Path
} else {
    'python'
}

$WorkRoot = if ($env:ASTRA_BUILD_WORK) { $env:ASTRA_BUILD_WORK } else { Join-Path $PSScriptRoot '.pyinstaller-build' }
$DistRoot = if ($env:ASTRA_BUILD_DIST) { $env:ASTRA_BUILD_DIST } else { Join-Path $PSScriptRoot 'release' }

$SharedArgs = @(
    '--noconfirm', '--clean', '--onefile', '--windowed', '--distpath', $DistRoot,
    '--paths', '.', '--paths', 'backend', '--paths', 'security', '--paths', 'ai-companion',
    '--paths', 'backend/engine', '--paths', 'backend/link',
    '--paths', 'backend/simulators', '--paths', 'backend/ground-backend',
    '--add-data', 'backend/config;config', '--add-data', 'backend/contracts;contracts',
    '--add-data', 'backend/engine/defaults.yaml;engine', '--add-data', 'ai-companion/companion/content;companion/content',
    '--add-data', 'frontend/web-astronaut/dist;web-astronaut/dist',
    '--add-data', 'frontend/web-ground/dist;web-ground/dist',
    '--hidden-import', 'astra_security', '--hidden-import', 'astra_engine',
    '--hidden-import', 'astra_link', '--hidden-import', 'astra_ground',
    '--hidden-import', 'hub', '--hidden-import', 'companion'
)

Invoke-Native $Python (@('-m', 'PyInstaller') + $SharedArgs + @('--name', $AstronautName, '--workpath', (Join-Path $WorkRoot 'astronaut'), 'launcher.py')) "PyInstaller failed to create $DistRoot/$AstronautName.exe."

Invoke-Native $Python (@('-m', 'PyInstaller') + $SharedArgs + @('--name', $GroundStationName, '--workpath', (Join-Path $WorkRoot 'ground'), 'launcher.py')) "PyInstaller failed to create $DistRoot/$GroundStationName.exe."

$OldSingleApp = Join-Path $DistRoot 'Astra.exe'
if (Test-Path -LiteralPath $OldSingleApp -PathType Leaf) {
    Remove-Item -LiteralPath $OldSingleApp
}
Write-Host "Ready: $DistRoot\$AstronautName.exe"
Write-Host "Ready: $DistRoot\$GroundStationName.exe"
