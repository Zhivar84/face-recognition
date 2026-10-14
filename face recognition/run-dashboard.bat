@echo off
rem Starts the Persian dashboard with the project's own Python (.venv) and restarts it if it dies.
rem Keep this window open while using the dashboard. Close it (or Ctrl+C) to stop.
setlocal
cd /d "%~dp0"
title Face Attendance Dashboard - keep this window open
echo.
echo Starting dashboard...  http://127.0.0.1:8050
echo Keep this window open. If the server stops it restarts automatically.
echo.
start "" "http://127.0.0.1:8050"
:loop
.venv\Scripts\python.exe dashboard.py
echo.
echo Dashboard stopped (exit code %errorlevel%). Restarting in 3 seconds... press Ctrl+C to quit.
timeout /t 3 /nobreak >nul
goto loop
