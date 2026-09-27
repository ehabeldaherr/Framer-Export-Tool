@echo off
cd /d "%~dp0"
echo Creating Desktop shortcut for Framer Export Tool...

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $d = [Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut((Join-Path $d 'Framer Export Tool.lnk')); $s.TargetPath = '%~dp0Run Framer Exporter.bat'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Launch Framer Export Tool'; $s.Save()"

echo.
echo [SUCCESS] Desktop shortcut created: "Framer Export Tool" on your Desktop!
echo.
pause
