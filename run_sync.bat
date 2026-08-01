@echo off
REM Dispatch Synchronization Utility — Pull approved records from VPS
REM Usage: run_sync.bat [--dry-run] [--verbose]

cd /d "%~dp0"
python run_sync.py %*
if errorlevel 2 (
    echo.
    echo SYNC FAILED — check logs in sync_data\logs\
) else if errorlevel 1 (
    echo.
    echo SYNC PARTIAL — some errors occurred, check logs in sync_data\logs\
) else (
    echo.
    echo SYNC COMPLETE
)
pause
