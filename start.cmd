@echo off
setlocal
cd /d "%~dp0"
uv run --locked python -B -X utf8 -m medplatform %*
exit /b %errorlevel%
