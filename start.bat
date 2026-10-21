@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title BioLearn AI - start

echo ============================================
echo  BioLearn AI V1.0
echo ============================================
echo.

set "PYTHON=%~dp0backend\.venv\Scripts\python.exe"
set "PORT=8000"
set "HOST=127.0.0.1"

if not exist "%PYTHON%" (
  echo [ERROR] 未找到后端运行环境 backend\.venv。
  echo         请先双击运行 install.bat 完成安装。
  goto :fail
)

if not exist "%~dp0frontend\dist\index.html" (
  echo [WARN] 未找到前端构建产物 frontend\dist\index.html。
  echo        当前只能使用 API；请运行 build_frontend.bat 生成界面。
  echo.
)

echo [INFO] 检查端口 %PORT% ...
"%PYTHON%" "%~dp0scripts\stop_services.py" --port %PORT% --check >nul 2>nul
if not errorlevel 1 (
  echo [ERROR] 端口 %PORT% 已被占用，可能 BioLearn AI 已经在运行。
  goto :fail
)

echo [INFO] 准备数据库与配置 ...
"%PYTHON%" "%~dp0scripts\prepare_env.py"
if errorlevel 1 (
  echo [ERROR] 初始化失败，请查看上面的提示。
  goto :fail
)
echo.

echo [INFO] 启动服务：http://%HOST%:%PORT%/
echo [INFO] 关闭窗口或按 Ctrl+C 可停止服务（或双击 stop.bat）。
echo.
start "" "http://%HOST%:%PORT%/"
"%PYTHON%" "%~dp0scripts\run_backend.py" --host %HOST% --port %PORT%
set "CODE=%errorlevel%"

echo.
if not "%CODE%"=="0" (
  echo [ERROR] 服务异常退出（代码 %CODE%）。请查看上面的错误信息。
  echo        常见原因：端口被占用、依赖缺失、.env 配置错误。
  goto :fail
)
exit /b 0

:fail
echo.
pause
exit /b 1
