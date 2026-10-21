@echo off
rem Publish the V1.0.0 GitHub Release with the portable ZIP attached.
rem Uses the Git shipped with DSH plus the credential already stored on this PC.
setlocal
chcp 65001 >nul
set "GIT=C:\Users\bzlciallo\.dsh\profiles\desktop\node_modules\@dsh-ops\bash-win32-x64\ucrt64\bin\git.exe"
set "PYTHON=C:\Users\bzlciallo\Documents\Codex\2026-10-19\biolearn-ai-git-python-node-js\backend\.venv\Scripts\python.exe"
cd /d "%~dp0"

if not exist "%PYTHON%" (
  echo [ERROR] python not found: %PYTHON%
  pause
  exit /b 1
)

echo 正在发布 Release v1.0.0（会复用本机已保存的 GitHub 凭据）...
"%PYTHON%" "%~dp0scripts\publish_release.py"
set "CODE=%errorlevel%"
echo.
pause
exit /b %CODE%
