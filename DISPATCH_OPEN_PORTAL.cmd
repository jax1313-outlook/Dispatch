@echo off
REM ===================================================================
REM   DISPATCH - OPEN THE PORTAL
REM
REM   Double-click this file to open Dispatch in your browser when it is
REM   ALREADY RUNNING. Use it when you closed the browser tab and want it
REM   back, or when the launcher window is minimised somewhere.
REM
REM   This file does NOT start Dispatch, deliberately. Starting it here
REM   would leave a server running with no window to stop it -- and the
REM   window opened by DISPATCH_START_HERE is the on/off switch. Use that
REM   file to start; use this one to get back to the page.
REM ===================================================================
REM
REM   Like DISPATCH_START_HERE, this holds no logic. A batch file cannot
REM   be tested. Everything it decides lives in dispatch_launcher, which
REM   the suite exercises.

setlocal
cd /d "%~dp0"
title Dispatch - Open Portal

chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"

set "DISPATCH_PY=py -3"
where py >nul 2>&1 || set "DISPATCH_PY=python"

%DISPATCH_PY% -c "import sys" >nul 2>&1
if errorlevel 1 goto :no_python

%DISPATCH_PY% -m dispatch_launcher open
echo.

REM The window always waits, success included. If Dispatch is not running,
REM the message above says so and says what to do instead -- and a window
REM that closed on its own would throw exactly that away.
pause
exit /b 0

:no_python
echo.
echo   Dispatch needs Python, and Python is not installed on this machine.
echo.
echo   Double-click DISPATCH_START_HERE instead. It explains how to
echo   install Python, step by step.
echo.
pause
exit /b 9009
