@echo off
REM Dispatch D:\ Drive Migration Utility — Transfer workspace creations to D:\ drive
REM Usage: run_bootstrap_d_drive.bat [--dry-run] [--verbose]

cd /d "%~dp0"
python bootstrap_d_drive.py %*
if errorlevel 1 (
    echo.
    echo BOOTSTRAP FAILED — check output logs above
) else (
    echo.
    echo BOOTSTRAP COMPLETE
)
pause
