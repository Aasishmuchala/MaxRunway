$ErrorActionPreference = 'Stop'
$destination = Join-Path $env:APPDATA 'Autodesk\ApplicationPlugins\MaxRunway.bundle'
if (-not (Test-Path -LiteralPath $destination)) {
    Write-Host 'MaxRunway is not installed for this Windows user.'
    exit 0
}
$archiveRoot = Join-Path $env:LOCALAPPDATA 'MaxRunway\uninstalled'
New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
$archive = Join-Path $archiveRoot ('MaxRunway.bundle-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
Move-Item -LiteralPath $destination -Destination $archive
Write-Host ('MaxRunway was removed from 3ds Max and retained at ' + $archive)
Write-Host 'Settings and credentials were not deleted.'
