param([switch]$Phone, [switch]$Build)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Please install and start Docker Desktop, then run this script again.'
}
$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    & docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw 'Docker did not become ready within two minutes. Start Docker Desktop and try again.' }
$composeArgs = @('compose', '-f', 'compose.yaml')
if ($Phone) { $composeArgs += @('-f', 'compose.phone.yaml') }
$composeArgs += @('up', '-d')
if ($Build) { $composeArgs += '--build' }
& docker @composeArgs
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose failed. Check the output above.' }
Start-Process 'http://localhost:8765'
