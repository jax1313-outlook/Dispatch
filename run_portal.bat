@echo off
REM ===================================================================
REM   run_portal.bat - SUPERSEDED. This file now hands over.
REM
REM   It used to run `python portal\app.py` directly, which started a
REM   real Dispatch server on port 8080 that the launcher had no record
REM   of. That is not a harmless shortcut. It produced, on a real
REM   machine on 2026-08-29:
REM
REM     - a server holding port 8080 with no window that could stop it
REM     - Start refusing every time, because the port was taken
REM     - Stop reporting "Dispatch is not running. Nothing to stop."
REM     - a portal page that loaded perfectly, from a build nobody chose
REM
REM   The operator found this file by looking through folders for a
REM   "run" file to double-click, which is exactly what someone does
REM   when they cannot remember which file starts the program. A launcher
REM   that refuses to start a second server is defeated by a file beside
REM   it that starts one without asking. A comment saying "superseded"
REM   is not a guard; this is.
REM
REM   Nothing is lost. A developer who wants the unmanaged server still
REM   has `python portal/app.py`, which is a deliberate act rather than
REM   a double-click.
REM ===================================================================

setlocal
cd /d "%~dp0"

echo.
echo   run_portal.bat is superseded and no longer starts a server of its own.
echo.
echo   Starting Dispatch through the launcher instead, so that Stop, Restart
echo   and status all know about it.
echo.

call "%~dp0DISPATCH_START_HERE.cmd"
exit /b %ERRORLEVEL%
