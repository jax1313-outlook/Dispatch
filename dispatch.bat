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

REM Ask for the UTF-8 code page so the Control Center menu can draw its icons.
REM Failure here is fine and is not reported: dispatch_launcher.glyphs asks the
REM output stream whether it can encode them and simply omits them if not, so a
REM console stuck on cp437 gets a clean menu rather than mojibake or a crash.
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"

REM Prefer the Windows Python launcher (py.exe), which is installed with
REM Python on Windows and picks a real interpreter even when PATH does not.
set "DISPATCH_PY=py -3"
where py >nul 2>&1 || set "DISPATCH_PY=python"

%DISPATCH_PY% -m dispatch_launcher %*
set "DISPATCH_EXIT=%ERRORLEVEL%"

if "%~1"=="" goto :held_open
exit /b %DISPATCH_EXIT%

REM Double-clicked with no arguments: the console window closes the instant this
REM file ends, so it is held open UNCONDITIONALLY -- success included.
REM
REM It used to pause only on a non-zero exit, and that threw away the one thing
REM the operator needed. `run_menu` returns 0 when it reads EOF on stdin, so a
REM window without usable keyboard input printed the whole status block, quit
REM cleanly, and disappeared before any of it could be read. Reported exactly
REM that way: "a black screen that flashed and I almost could read".
REM
REM A window that closes on its own is a window that decided the operator did
REM not need to see what it said. That decision is not this file's to make.
:held_open
echo.
if not "%DISPATCH_EXIT%"=="0" (
  echo   Dispatch Launcher exited with code %DISPATCH_EXIT%.
  echo.
)
pause
exit /b %DISPATCH_EXIT%
