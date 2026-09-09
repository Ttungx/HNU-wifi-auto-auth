@echo off
chcp 65001 >nul
title 校园网自动认证 - 卸载程序
echo 正在注销 Windows 计划任务 CampusWiFiAutoAuth...
schtasks /delete /tn "CampusWiFiAutoAuth" /f >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [+] 任务计划 CampusWiFiAutoAuth 已成功删除。
) else (
    echo [-] 任务计划不存在或已被删除。
)
echo.
echo 请按任意键退出...
pause >nul
