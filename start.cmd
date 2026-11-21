@echo off
setlocal
cd /d "%~dp0"
set "args=%*"
if "%~1"=="" set "args=serve"
if "%~1"=="" goto build
if not "%~1"=="serve" goto run
:build
call pnpm install --frozen-lockfile || exit /b
call pnpm build || exit /b
:run
cd backend
uv run --locked python -B -X utf8 -m medplatform %args%
exit /b %errorlevel%
