@echo off
REM -------------------------------------------------
REM Simple wrapper that launches the Life Calendar GUI.
REM The binary already lives in the same folder; launching it
REM directly is enough, but Windows users sometimes expect an
REM *.bat installer.
REM -------------------------------------------------
set "ROOT_DIR=%~dp0.."

if exist "%ROOT_DIR%\LifeCalendar.exe" (
    start "" "%ROOT_DIR%\LifeCalendar.exe"
) else (
    echo LifeCalendar.exe not found – running from source instead.
    python "%ROOT_DIR%\life_calendar_gui.py"
)
