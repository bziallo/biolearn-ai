@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title BioLearn AI - restore

set "PYTHON=%~dp0backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo ============================================
echo  BioLearn AI V1.0 - 从备份恢复
echo ============================================
echo.
echo 步骤：
echo   1) 先运行 stop.bat 停止服务
echo   2) 把备份目录（包含 biolearn.db）拖到本窗口，按回车
echo   3) 当前数据会被移动到 backend\data\_restore_previous_*，不会删除
echo.
set /p "BACKUP_DIR=备份目录： "
if "%BACKUP_DIR%"=="" (
  echo [ERROR] 未提供备份目录。
  pause
  exit /b 1
)

"%PYTHON%" "%~dp0scripts\restore_data.py" "%BACKUP_DIR%" --force
echo.
pause
exit /b 0
