@echo off
rem Push the v1.0.0 tag using the Git shipped with DSH (no system Git needed).
setlocal
chcp 65001 >nul
set "GIT=C:\Users\bzlciallo\.dsh\profiles\desktop\node_modules\@dsh-ops\bash-win32-x64\ucrt64\bin\git.exe"
cd /d "%~dp0"

if not exist "%GIT%" (
  echo [ERROR] 未找到 git.exe，请安装 Git for Windows 后重试。
  pause
  exit /b 1
)

echo 使用：%GIT%
echo.
"%GIT%" --version
echo.
echo 正在推送标签 v1.0.0（首次会弹出 GitHub 登录窗口）...
"%GIT%" push origin v1.0.0
set "CODE=%errorlevel%"
echo.
if "%CODE%"=="0" (
  echo [OK] 标签已推送。现在可以发布 Release：
  echo      https://github.com/bziallo/biolearn-ai/releases/new
) else (
  echo [ERROR] 推送失败，代码 %CODE%。
)
echo.
pause
exit /b %CODE%
