"""Write the portable-build launcher scripts.

The portable distribution has no virtualenv; it ships python/python.exe at the
distribution root. start.bat must therefore resolve its interpreter locally
instead of backend\\.venv\\Scripts\\python.exe.

Usage: python scripts/portable_launchers.py <target-dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

START = r"""@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title BioLearn AI

set "PYTHON=%~dp0python\python.exe"
set "PORT=8000"
set "HOST=127.0.0.1"

if not exist "%PYTHON%" (
  echo [ERROR] Install is incomplete: python\python.exe is missing.
  echo         Please re-extract the portable ZIP.
  goto :fail
)

if not exist "%~dp0frontend\dist\index.html" (
  echo [ERROR] Install is incomplete: frontend\dist\index.html is missing.
  echo         Please re-extract the portable ZIP.
  goto :fail
)

echo [INFO] Checking port %PORT% ...
"%PYTHON%" "%~dp0scripts\stop_services.py" --port %PORT% --check >nul 2>nul
if not errorlevel 1 (
  echo [ERROR] Port %PORT% is already in use. BioLearn AI may already be running.
  echo         Run stop.bat first, then start again.
  goto :fail
)

echo [INFO] Preparing database and configuration ...
"%PYTHON%" "%~dp0scripts\prepare_env.py"
if errorlevel 1 (
  echo [ERROR] Initialization failed. See the messages above.
  goto :fail
)
echo.

echo [INFO] Starting BioLearn AI: http://%HOST%:%PORT%/
echo [INFO] Close this window or press Ctrl+C to stop.
echo.
start "" "http://%HOST%:%PORT%/"
"%PYTHON%" "%~dp0scripts\run_backend.py" --host %HOST% --port %PORT%
set "CODE=%errorlevel%"

echo.
if not "%CODE%"=="0" (
  echo [ERROR] Service exited with code %CODE%.
  goto :fail
)
exit /b 0

:fail
echo.
pause
exit /b 1
"""

STOP = r"""@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHON=%~dp0python\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
echo Stopping BioLearn AI ...
"%PYTHON%" "%~dp0scripts\stop_services.py" --port 8000
echo.
pause
exit /b 0
"""

BACKUP = r"""@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHON=%~dp0python\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
echo Backing up BioLearn AI data ...
echo Close the server window first for a consistent copy.
echo.
"%PYTHON%" "%~dp0scripts\backup_data.py"
echo.
pause
exit /b 0
"""

RESTORE = r"""@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHON=%~dp0python\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
echo Restore BioLearn AI data from a backup folder.
echo Current data is moved to data\_restore_previous_* (never deleted).
echo.
set /p "BACKUP_DIR=Backup folder: "
if "%BACKUP_DIR%"=="" (
  echo [ERROR] No folder given.
  pause
  exit /b 1
)
"%PYTHON%" "%~dp0scripts\restore_data.py" "%BACKUP_DIR%" --force
echo.
pause
exit /b 0
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: portable_launchers.py <target-dir>")
        return 2
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    files = {
        "start.bat": START,
        "stop.bat": STOP,
        "backup.bat": BACKUP,
        "restore.bat": RESTORE,
    }
    for name, content in files.items():
        path = target / name
        path.write_bytes(content.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
        print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
