@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title BioLearn AI - dev

echo ============================================
echo  BioLearn AI V1.0 - 开发模式（热更新）
echo ============================================
echo.

set "PYTHON=%~dp0backend\.venv\Scripts\python.exe"
set "PORT=8000"
set "HOST=127.0.0.1"

if not exist "%PYTHON%" (
  echo [ERROR] 未找到 backend\.venv，请先运行 install.bat。
  goto :fail
)

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 开发模式需要 Node.js（Vite）。日常使用请直接双击 start.bat。
  goto :fail
)

"%PYTHON%" "%~dp0scripts\stop_services.py" --port %PORT% --check >nul 2>nul
if not errorlevel 1 (
  echo [ERROR] 端口 %PORT% 已被占用，请先运行 stop.bat。
  goto :fail
)

"%PYTHON%" "%~dp0scripts\prepare_env.py"
if errorlevel 1 goto :fail

echo [INFO] 启动后端（自动重载）...
start "BioLearn backend (dev)" "%PYTHON%" "%~dp0scripts\run_backend.py" --host %HOST% --port %PORT% --reload

pushd "%~dp0frontend"
if exist node_modules (
  echo [INFO] 启动 Vite 开发服务器：http://127.0.0.1:5173/
  start "" "http://127.0.0.1:5173/"
  call npm run dev -- --host 127.0.0.1 --port 5173
) else (
  where pnpm >nul 2>nul
  if errorlevel 1 (
    call npm install
    call npm run dev -- --host 127.0.0.1 --port 5173
  ) else (
    call pnpm install
    call pnpm dev -- --host 127.0.0.1 --port 5173
  )
)
popd
exit /b 0

:fail
echo.
pause
exit /b 1
