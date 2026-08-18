@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Checking Python...
if exist ".runtime\python.exe" (
    ".runtime\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_BOOTSTRAP=.runtime\python.exe"
        goto create_environment
    )
)

where py >nul 2>nul
if errorlevel 1 goto try_python_command
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 goto use_py_launcher

:try_python_command
where python >nul 2>nul
if errorlevel 1 goto python_missing
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto python_missing
set "PYTHON_BOOTSTRAP=python"
goto create_environment

:use_py_launcher
set "PYTHON_BOOTSTRAP=py -3"

:create_environment
echo [2/3] Creating local environment if needed...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
    if errorlevel 1 (
        echo The existing .venv is broken or its base Python was removed. Repairing it...
        %PYTHON_BOOTSTRAP% -m venv --clear .venv
        if errorlevel 1 goto failed
    )
) else (
    %PYTHON_BOOTSTRAP% -m venv .venv
    if errorlevel 1 goto failed
)

echo [3/3] Installing required packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

cscript //nologo "app\config\create_shortcut.vbs" "%CD%"
if errorlevel 1 (
    echo Warning: setup completed, but the graphical shortcut could not be created.
)

echo.
echo Setup complete.
echo Double-click "Lalikul Cut Prep.lnk" to start with the app icon and no terminal.
echo If the shortcut is unavailable, use "Lalikul Cut Prep.vbs".
echo Use run_console.bat only if you need to diagnose an error.
pause
exit /b 0

:python_missing
echo.
echo Python 3 was not found.
echo This project normally includes its own Python runtime in .runtime.
echo If that folder was removed, restore the complete project or reinstall Python.
echo Install Python 3.10 or newer from https://www.python.org/downloads/windows/
echo During installation, enable "Add python.exe to PATH", then run setup.bat again.
pause
exit /b 1

:failed
echo.
echo Setup failed. Review the messages above and try again.
pause
exit /b 1
