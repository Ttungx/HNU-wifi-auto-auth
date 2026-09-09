@echo off
cd /d "%~dp0"
python install_task.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Installation failed with error code %ERRORLEVEL%.
    echo [!] Please ensure Python is installed and added to PATH.
)
echo.
pause
