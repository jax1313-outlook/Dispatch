@echo off
REM ===================================================================
REM   DISPATCH - START HERE
REM
REM   Double-click this file. Dispatch starts and opens in your browser.
REM   Nothing to type. Nothing to install. Nothing to set up first.
REM
REM   To stop Dispatch, press any key in the window this opens.
REM ===================================================================
REM
REM   This file deliberately holds no logic. A batch file cannot be
REM   tested, and this is the very first code path a new operator meets,
REM   so it must be the least likely thing in the repository to be wrong.
REM   Everything it decides lives in dispatch_launcher/first_run.py, which
REM   the test suite exercises. All this does is find an interpreter, hand
REM   over, and refuse to let the window vanish before the message is read.

setlocal
cd /d "%~dp0"
title Dispatch

REM Ask for UTF-8 so the status block draws cleanly. Failure is fine and is
REM not reported -- the launcher drops its icons rather than printing mojibake.
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"

REM py.exe ships with Python on Windows and finds a real interpreter even when
REM PATH does not. Fall back to python for an install that skipped the launcher.
set "DISPATCH_PY=py -3"
where py >nul 2>&1 || set "DISPATCH_PY=python"

REM Is there a Python at all? This is the one failure that has to be caught
REM here rather than in Python, for the obvious reason.
%DISPATCH_PY% -c "import sys" >nul 2>&1
if errorlevel 1 goto :no_python

%DISPATCH_PY% -m dispatch_launcher start-here
set "DISPATCH_EXIT=%ERRORLEVEL%"

if not "%DISPATCH_EXIT%"=="0" goto :did_not_start

REM Running. The window is now the on/off switch: open means Dispatch is up.
pause >nul
echo.
echo   Stopping Dispatch...
%DISPATCH_PY% -m dispatch_launcher stop
echo.
echo   Dispatch has stopped. You can close this window.
echo.
pause
exit /b 0

:did_not_start
echo.
echo   Dispatch did not start. The reason is printed above.
echo.
echo   Nothing was damaged and nothing was lost. Fix the item marked STOP
echo   and double-click this file again.
echo.
pause
exit /b %DISPATCH_EXIT%

:no_python
echo.
echo   ==============================================================
echo    DISPATCH CANNOT START - Python is not installed
echo   ==============================================================
echo.
echo   Dispatch needs Python. It is free, it takes a few minutes, and
echo   you only do this once.
echo.
echo     1. Go to:  https://www.python.org/downloads/
echo     2. Click the big yellow "Download Python" button.
echo     3. Run the file it downloads.
echo     4. IMPORTANT: tick "Add Python to PATH" on the first screen
echo        before you click Install. It is easy to miss.
echo     5. When it finishes, double-click DISPATCH_START_HERE again.
echo.
echo   Nothing is broken. Dispatch simply has nothing to run on yet.
echo.
pause
exit /b 9009
