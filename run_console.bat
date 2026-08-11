@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The local environment is missing. Run setup.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo The local environment is broken or its base Python was removed.
    echo Run setup.bat again to repair it.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m app.main
if errorlevel 1 (
    echo.
    echo The application closed because of an error.
    pause
)
