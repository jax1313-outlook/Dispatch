@echo off
REM  DISPATCH - START IN REHEARSAL MODE
REM
REM  Double-click this. Same Dispatch, same screens, same database -- but
REM  everything created while this window is open is TAGGED AS REHEARSAL at the
REM  moment it is created, and marked as rehearsal wherever it is displayed.
REM
REM  Use this to try something out.
REM  Use DISPATCH_START_HERE.cmd for real work.
REM
REM  All the work is in scripts\dispatch_rehearsal.py, on purpose: the session
REM  id must never pass through a batch variable, because the failure mode of a
REM  quoting mistake there is Dispatch starting UNTAGGED.

chcp 65001 >nul 2>&1
cd /d "%~dp0"
title DISPATCH - REHEARSAL MODE
set PYTHONIOENCODING=utf-8

py -3 scripts\dispatch_rehearsal.py

echo.
pause
