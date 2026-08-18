@echo off
setlocal
cd /d "%~dp0"

if not exist ".runtime\python.exe" (
    echo The local application runtime is missing. Run setup.bat first.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo The local application environment is missing. Run setup.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo The local environment is broken.
    echo Run setup.bat again to repair it.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m app.main
if errorlevel 1 (
    echo.
    echo The application closed because of an error.
    pause
)
