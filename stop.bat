@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title BioLearn AI - stop

set "PYTHON=%~dp0backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo ============================================
echo  BioLearn AI V1.0 - 停止服务
echo ============================================
echo.
"%PYTHON%" "%~dp0scripts\stop_services.py" --port 8000
echo.
echo 数据保存在 backend\data，可随时再次启动。
pause
exit /b 0
