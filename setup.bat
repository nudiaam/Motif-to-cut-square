@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Checking Python...
if exist ".runtime\python.exe" (
    ".runtime\python.exe" -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 15) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_BOOTSTRAP=.runtime\python.exe"
        goto create_environment
    )
)

where py >nul 2>nul
if errorlevel 1 goto try_python_command
py -3 -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 15) else 1)" >nul 2>nul
if not errorlevel 1 goto use_py_launcher

:try_python_command
where python >nul 2>nul
if errorlevel 1 goto python_missing
python -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info < (3, 15) else 1)" >nul 2>nul
if errorlevel 1 goto python_missing
set "PYTHON_BOOTSTRAP=python"
goto create_environment

:use_py_launcher
set "PYTHON_BOOTSTRAP=py -3"

:create_environment
%PYTHON_BOOTSTRAP% -c "import os,sys; raise SystemExit(0 if len(os.path.abspath('.')) <= 70 else 1)"
if errorlevel 1 goto folder_too_long
echo [2/4] Creating local environment if needed...
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

echo [3/4] Installing required packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo [4/4] Verifying the installed application and bundled files...
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m app.config.check_installation
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
echo A compatible Python 3.10 to 3.14 was not found.
echo Install Python 3.12 (64-bit, recommended) from https://www.python.org/downloads/windows/
echo During installation, enable "Add python.exe to PATH", then run setup.bat again.
pause
exit /b 1

:failed
echo.
echo Setup failed. Review the messages above and try again.
pause
exit /b 1

:folder_too_long
echo.
echo This folder path is too long for a reliable Windows installation.
echo Extract the complete ZIP into a shorter folder, such as Desktop\Lalikul.
echo Then run setup.bat from that new folder. Do not copy an old .venv folder.
pause
exit /b 1
