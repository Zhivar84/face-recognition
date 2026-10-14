@echo off
rem Starts the Persian dashboard using the project's own Python (.venv).
rem Double-click this file, then open or refresh http://127.0.0.1:8050 in your browser.
cd /d "%~dp0"
title Face Attendance Dashboard - keep this window open
echo.
echo Starting dashboard... when it is ready open:  http://127.0.0.1:8050
echo Keep this window open while using the dashboard. Close it (or Ctrl+C) to stop.
echo.
.venv\Scripts\python.exe dashboard.py
echo.
echo Dashboard stopped. If you saw an error above, read it carefully.
pause
