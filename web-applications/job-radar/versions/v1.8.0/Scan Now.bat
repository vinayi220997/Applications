@echo off
title Job Radar - scan
cd /d "%~dp0"
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY="%%D\python.exe""
if not defined PY (
  echo Python 3.9 or newer is needed. Run JobRadar-Setup.exe again, or install it from https://www.python.org/downloads/
  echo ^(tick "Add python.exe to PATH"^), then start Job Radar again.
  pause
  exit /b 1
)
echo Scanning job sources...
%PY% -m jobradar run
if errorlevel 1 pause
pause
