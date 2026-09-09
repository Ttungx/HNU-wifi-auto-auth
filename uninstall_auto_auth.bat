@echo off
cd /d "%~dp0"
schtasks /delete /tn "CampusWiFiAutoAuth" /f >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [+] Scheduled task CampusWiFiAutoAuth successfully removed.
) else (
    echo [-] Task not found or already removed.
)
echo.
pause
