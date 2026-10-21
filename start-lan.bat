@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title BioLearn AI - laptop LAN mode

echo ============================================
echo  BioLearn AI - 局域网模式（手机可访问）
echo ============================================
echo.
echo 警告：本模式会监听 0.0.0.0，同一网段的设备都能访问。
echo 强烈建议先在 .env 中设置 ACCESS_TOKEN（共享口令）。
echo 不要在公共 Wi-Fi 或直接公网环境下使用本脚本。
echo.
pause

set "PYTHON=%~dp0backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
set "PORT=8000"

"%PYTHON%" "%~dp0scripts\prepare_env.py"
if errorlevel 1 goto :fail

echo.
echo 手机 App 中填写：http://^<本机 IPv4^>:%PORT%/api/v1
echo 查看本机 IPv4：ipconfig
echo.
"%PYTHON%" "%~dp0scripts\run_backend.py" --lan --port %PORT%
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
pause
exit /b 1
