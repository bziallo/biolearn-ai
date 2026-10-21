@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title BioLearn AI - build frontend

echo ============================================
echo  BioLearn AI V1.0 - 构建前端
echo ============================================
echo.

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 未找到 node 命令。
  echo         请安装 Node.js 20.19+（https://nodejs.org/）后重试。
  goto :fail
)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo [INFO] 未找到 pnpm，尝试使用 npm 安装依赖 ...
  pushd "%~dp0frontend"
  call npm install
  if errorlevel 1 (
    popd
    echo [ERROR] 依赖安装失败。
    goto :fail
  )
  call npm run build
  set "RESULT=!errorlevel!"
  popd
) else (
  pushd "%~dp0frontend"
  call pnpm install
  if errorlevel 1 (
    popd
    echo [ERROR] 依赖安装失败。
    goto :fail
  )
  call pnpm build
  set "RESULT=!errorlevel!"
  popd
)

if not "!RESULT!"=="0" (
  echo [ERROR] 前端构建失败，请查看上面的 TypeScript/Vite 错误。
  goto :fail
)

if not exist "%~dp0frontend\dist\index.html" (
  echo [ERROR] 构建结束但未找到 frontend\dist\index.html。
  goto :fail
)

echo.
echo [OK]   前端已构建到 frontend\dist。
echo        后端会直接托管该目录，无需单独启动前端服务。
pause
exit /b 0

:fail
pause
exit /b 1
