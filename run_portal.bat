@echo off
REM Dispatch Operations Portal - local launcher (superseded by dispatch.bat)
REM Run from the project root: .\run_portal.bat
REM Prefer dispatch.bat, which adds Stop, Restart, status and PID handling.

echo.
echo   Dispatch Operations Portal
echo   Starting on http://127.0.0.1:8080
echo.

python portal\app.py
