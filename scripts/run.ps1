param(
    [ValidateSet('serve', 'init-db', 'migrate', 'db-status', 'seed-demo')]
    [string]$Command = 'serve'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        throw 'Run scripts/setup.ps1 first.'
    }
    & ./.venv/Scripts/python.exe -X utf8 -m medplatform $Command
    if ($LASTEXITCODE -ne 0) { throw 'Operation failed. See docs run instructions.' }
} finally { Pop-Location }
