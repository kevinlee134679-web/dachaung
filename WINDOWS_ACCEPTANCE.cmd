@echo off
setlocal
cd /d "%~dp0"
py -3.14 -B -X utf8 scripts\accept_windows.py
set "ACCEPT_RESULT=%errorlevel%"
if not "%ACCEPT_RESULT%"=="0" echo Acceptance did not pass. See the result summary above.
echo.
pause
exit /b %ACCEPT_RESULT%
