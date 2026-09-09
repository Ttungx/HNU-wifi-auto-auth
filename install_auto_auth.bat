@echo off
chcp 65001 >nul
title 校园网自动认证 - 安装程序
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_task.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] 若提示权限不足，请右键点击本 bat 文件选择「以管理员身份运行」。
)

echo.
echo 请按任意键退出...
pause >nul
