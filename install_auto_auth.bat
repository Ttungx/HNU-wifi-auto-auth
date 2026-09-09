@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_task.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Installation failed with error code %ERRORLEVEL%.
    echo [!] Please right-click this file and select "Run as administrator".
)
echo.
pause
