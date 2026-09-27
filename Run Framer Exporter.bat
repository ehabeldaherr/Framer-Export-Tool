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
echo [!] Keep this window open while using the tool.
echo [!] To stop the tool, simply close this window.
echo ========================================================
echo.

:: Open browser after a 2-second delay to ensure Flask has started
start "" powershell -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:5000/'"

:: Try running with python
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python app.py
    if %ERRORLEVEL% NEQ 0 pause
    goto end
)

:: Fallback to py launcher if python command not in path
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py app.py
    if %ERRORLEVEL% NEQ 0 pause
    goto end
)

echo.
echo ========================================================
echo [ERROR] Python was not found on your system PATH!
echo Please make sure Python is installed and added to PATH.
echo ========================================================
pause

:end
