@echo off
title Framer Export Tool
cd /d "%~dp0"

echo ========================================================
echo              Framer Export Tool Launcher
echo ========================================================
echo.
echo Starting web server at http://127.0.0.1:5000/ ...
echo Opening your default browser...
echo.
echo ========================================================
echo   [!] IMPORTANT: KEEP THIS BLACK WINDOW OPEN!
echo   [!] If you close this window, the tool will stop.
echo ========================================================
echo.

start "" powershell -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:5000/'"

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python app.py
    if %ERRORLEVEL% NEQ 0 pause
    goto end
)

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py app.py
    if %ERRORLEVEL% NEQ 0 pause
    goto end
)

echo.
echo ========================================================
echo [ERROR] Python was not found on your system PATH!
echo ========================================================
pause

:end