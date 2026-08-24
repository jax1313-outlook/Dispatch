@echo off
REM Dispatch - Operations Control
REM Double-click this file to start, stop, restart or open Dispatch.
REM
REM This wrapper deliberately does almost nothing. Every decision - whether
REM Dispatch is running, which process is the server, whether it is safe to
REM start a second one - lives in the dispatch_launcher Python package, which
REM the repository test suite exercises. A batch file cannot be tested, so a
REM batch file is not allowed to hold logic.

setlocal
cd /d "%~dp0"

REM Prefer the Windows Python launcher (py.exe), which is installed with
REM Python on Windows and picks a real interpreter even when PATH does not.
set "DISPATCH_PY=py -3"
where py >nul 2>&1 || set "DISPATCH_PY=python"

%DISPATCH_PY% -m dispatch_launcher %*
set "DISPATCH_EXIT=%ERRORLEVEL%"

if "%~1"=="" goto :held_open
exit /b %DISPATCH_EXIT%

REM Double-clicked with no arguments: the console window closes the instant
REM this file ends, so hold it open long enough to read the last message.
:held_open
if not "%DISPATCH_EXIT%"=="0" (
  echo.
  echo   Dispatch Launcher exited with code %DISPATCH_EXIT%.
  echo.
  pause
)
exit /b %DISPATCH_EXIT%
