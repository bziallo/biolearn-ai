@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title BioLearn AI - install

echo ============================================
echo  BioLearn AI V1.0 - 安装依赖
echo ============================================
echo.

set "PYTHON=%~dp0backend\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo [INFO] 未找到 Python 虚拟环境，正在创建 backend\.venv ...
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] 未找到 python 命令。
    echo         请安装 Python 3.12+ 并勾选 "Add python.exe to PATH"。
    echo         下载：https://www.python.org/downloads/windows/
    goto :fail
  )
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
  if errorlevel 1 (
    echo [ERROR] Python 版本过低，需要 3.12 或更高版本。
    python --version
    goto :fail
  )
  python -m venv "%~dp0backend\.venv"
  if errorlevel 1 (
    echo [ERROR] 创建虚拟环境失败。
    goto :fail
  )
)

echo [INFO] 安装/更新后端依赖 ...
"%PYTHON%" -m pip install --upgrade pip >nul
"%PYTHON%" -m pip install -e "%~dp0backend"
if errorlevel 1 (
  echo [ERROR] 后端依赖安装失败，请检查网络后重试。
  goto :fail
)

echo.
echo [INFO] 检查前端构建产物 ...
if exist "%~dp0frontend\dist\index.html" (
  echo [OK]   已存在 frontend\dist，无需 Node.js。
) else (
  where node >nul 2>nul
  if errorlevel 1 (
    echo [WARN] 未找到 node 命令，且没有前端构建产物。
    echo        方案一：安装 Node.js 20+ 后重新运行 install.bat。
    echo        方案二：从发布包中直接复制 frontend\dist 目录。
  ) else (
    echo [INFO] 未找到前端构建产物，尝试构建 ...
    call "%~dp0build_frontend.bat"
  )
)

echo.
echo ============================================
echo  安装完成。下一步：
echo    1) 检查 .env（首次运行 start.bat 会自动生成）
echo    2) 双击 start.bat 启动系统
echo ============================================
pause
exit /b 0

:fail
echo.
echo 安装失败，请根据上面的提示处理后重试。
pause
exit /b 1
