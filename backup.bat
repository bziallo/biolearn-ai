@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title BioLearn AI - backup

set "PYTHON=%~dp0backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo ============================================
echo  BioLearn AI V1.0 - 备份数据
echo ============================================
echo.
echo 建议先运行 stop.bat 停止服务，确保数据一致。
echo.
pause

"%PYTHON%" "%~dp0scripts\backup_data.py"
echo.
pause
exit /b 0
