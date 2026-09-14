param([switch]$RepairDependencies)
$ErrorActionPreference = 'Stop'
$pluginRoot = $PSScriptRoot
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js 20.19 or newer, then rerun this script.'
}
Push-Location -LiteralPath (Join-Path $pluginRoot 'bridge')
try {
    if ($RepairDependencies -or -not (Test-Path -LiteralPath 'node_modules/mcp-remote/dist/proxy.js')) {
        & npm.cmd ci --ignore-scripts --no-fund --no-audit
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    }
    & npm.cmd test
    if ($LASTEXITCODE -ne 0) { throw 'Companion checks failed.' }
} finally { Pop-Location }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning 'FFmpeg and FFprobe are required for video encoding and output verification. Add both to PATH.'
}
if (-not (Get-Command codex -ErrorAction SilentlyContinue) -and -not $env:CODEX_CLI_PATH) {
    Write-Warning 'Codex is optional for rendering, but required for ChatGPT analysis and Codex-managed Runway MCP.'
}
Write-Host 'Ready. Installed bundles open after 3ds Max 2026 starts.'
Write-Host 'For a portable copy, use Scripting > Run Script > Launch_MaxRunway.ms.'
