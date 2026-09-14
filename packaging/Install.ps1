param([switch]$SkipChecks)
$ErrorActionPreference = 'Stop'
$packageRoot = $PSScriptRoot
$sourceBundle = Join-Path $packageRoot 'MaxRunway.bundle'
$manifest = Join-Path $packageRoot 'MANIFEST.sha256'

if (-not (Test-Path -LiteralPath (Join-Path $sourceBundle 'PackageContents.xml'))) {
    throw 'MaxRunway.bundle is missing or the archive was not fully extracted.'
}
if (-not $SkipChecks) {
    if (-not (Test-Path -LiteralPath $manifest)) { throw 'MANIFEST.sha256 is missing.' }
    foreach ($line in Get-Content -LiteralPath $manifest) {
        if (-not $line.Trim()) { continue }
        $parts = $line -split '  ', 2
        if ($parts.Count -ne 2) { throw 'Invalid package manifest.' }
        $file = Join-Path $packageRoot $parts[1]
        if (-not (Test-Path -LiteralPath $file)) { throw ('Package file is missing: ' + $parts[1]) }
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash.ToLowerInvariant()
        if ($actual -ne $parts[0]) { throw ('Package checksum mismatch: ' + $parts[1]) }
    }
}

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { Write-Warning 'Node.js 20.19+ is required for Runway generation and AI analysis.' }
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
if (-not $ffmpeg -or -not $ffprobe) { Write-Warning 'FFmpeg and FFprobe are required for sequences, output QC, and AI comparison.' }
if (-not (Get-Command codex -ErrorAction SilentlyContinue) -and -not $env:CODEX_CLI_PATH) {
    Write-Warning 'Codex is optional for rendering, but required for ChatGPT analysis and Codex-managed Runway MCP.'
}

$pluginParent = Join-Path $env:APPDATA 'Autodesk\ApplicationPlugins'
$destination = Join-Path $pluginParent 'MaxRunway.bundle'
New-Item -ItemType Directory -Path $pluginParent -Force | Out-Null
$backup = $null
if (Test-Path -LiteralPath $destination) {
    $backup = $destination + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Move-Item -LiteralPath $destination -Destination $backup
}
try {
    Copy-Item -LiteralPath $sourceBundle -Destination $destination -Recurse
} catch {
    if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Recurse -Force }
    if ($backup) { Move-Item -LiteralPath $backup -Destination $destination }
    throw
}
Write-Host ('Installed MaxRunway 0.2.0 to ' + $destination)
if ($backup) { Write-Host ('Previous installation retained at ' + $backup) }
Write-Host 'Restart 3ds Max 2026. The MaxRunway panel opens after startup.'
