@echo off
REM -------------------------------------------------
REM Simple wrapper that launches the Life Calendar GUI.
REM The binary already lives in the same folder; launching it
REM directly is enough, but Windows users sometimes expect an
REM *.bat installer.
REM -------------------------------------------------
if exist "LifeCalendar.exe" (
    start "" "%~dp0LifeCalendar.exe"
) else (
    echo LifeCalendar.exe not found – running from source instead.
    python "%~dp0life_calendar_gui.py"
)
