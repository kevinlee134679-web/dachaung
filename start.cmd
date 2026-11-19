@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -B -X utf8 run.py %*
) else (
  py -3.14 -B -X utf8 run.py %*
)
exit /b %errorlevel%
