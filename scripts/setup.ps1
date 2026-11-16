param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & $Python -X utf8 -c "import sys; assert sys.version_info[:2] == (3,14), 'CPython 3.14 required; tested 3.14.10'"
    if ($LASTEXITCODE -ne 0) { throw 'Python version check failed.' }
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        & $Python -X utf8 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    & ./.venv/Scripts/python.exe -X utf8 -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & ./.venv/Scripts/python.exe -X utf8 -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
} finally { Pop-Location }
