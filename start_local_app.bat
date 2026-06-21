@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE="
set "PYTHON_ARGS="

call :find_python

if not defined PYTHON_EXE (
  echo Python 3.9+ was not found.
  echo.
  echo Trying to install Python 3.12 with winget...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo winget was not found on this computer.
    echo Please install Python 3.12 manually from:
    echo https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )

  winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements --silent
  if errorlevel 1 (
    echo Failed to install Python with winget.
    echo Please install Python 3.12 manually from:
    echo https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )

  call :find_python
)

if not defined PYTHON_EXE (
  echo Python may have been installed, but this window cannot find it yet.
  echo Close this window and run start_local_app.bat again.
  pause
  exit /b 1
)

echo Using Python:
"%PYTHON_EXE%" %PYTHON_ARGS% --version
if errorlevel 1 (
  echo The detected Python command failed.
  pause
  exit /b 1
)

if not exist "eastmoney_reports" mkdir "eastmoney_reports"

echo Checking pip...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip --version >nul 2>nul
if errorlevel 1 (
  "%PYTHON_EXE%" %PYTHON_ARGS% -m ensurepip --upgrade
  if errorlevel 1 (
    echo Failed to enable pip.
    pause
    exit /b 1
  )
)

echo Installing or updating local app dependencies...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -e ".[app]"
if errorlevel 1 (
  echo Failed to install local app dependencies.
  pause
  exit /b 1
)

echo Importing existing outputs into local SQLite...
"%PYTHON_EXE%" %PYTHON_ARGS% -m eastmoney_report_scraper.cli import-existing --output-dir ".\eastmoney_reports"
if errorlevel 1 (
  echo Failed to import existing outputs.
  pause
  exit /b 1
)

echo Starting local app at http://127.0.0.1:8765 ...
"%PYTHON_EXE%" %PYTHON_ARGS% -m eastmoney_report_scraper.cli app --output-dir ".\eastmoney_reports" --port 8765 --open-browser

pause
exit /b 0

:find_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_EXE=python"
  set "PYTHON_ARGS="
  goto :eof
)

py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_EXE=py"
  set "PYTHON_ARGS=-3.12"
  goto :eof
)

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_EXE=py"
  set "PYTHON_ARGS=-3"
  goto :eof
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    set "PYTHON_ARGS="
    goto :eof
  )
)

if exist "%ProgramFiles%\Python312\python.exe" (
  "%ProgramFiles%\Python312\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
    set "PYTHON_ARGS="
    goto :eof
  )
)

goto :eof
