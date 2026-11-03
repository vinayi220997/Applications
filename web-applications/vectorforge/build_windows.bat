@echo off
setlocal enableextensions
title Build Vectorforge.exe
cd /d "%~dp0"

echo.
echo  Building Vectorforge for Windows
echo  ================================
echo.

rem ---- find Python 3.10+ -------------------------------------------------------------
set "PY="
where py >nul 2>nul && (py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=py -3")
if not defined PY (
  where python >nul 2>nul && (python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=python")
)
if not defined PY (
  echo  Python 3.10 or newer was not found.
  echo  Install it from https://www.python.org/downloads/windows/
  echo  and tick "Add python.exe to PATH" during setup, then run this file again.
  echo.
  pause
  exit /b 1
)
echo  Using: %PY%

rem ---- build environment -------------------------------------------------------------
if not exist ".build-venv\Scripts\python.exe" (
  echo  Creating build environment...
  %PY% -m venv .build-venv || goto :fail
)
set "VPY=.build-venv\Scripts\python.exe"
echo  Installing dependencies (first run downloads about 150 MB)...
"%VPY%" -m pip install --upgrade pip >nul || goto :fail
"%VPY%" -m pip install -r requirements.txt pyinstaller || goto :fail

rem ---- build the app ------------------------------------------------------------------
echo  Packaging with PyInstaller (takes a few minutes)...
"%VPY%" -m PyInstaller packaging\vectorforge.spec --noconfirm --clean || goto :fail

echo.
echo  App built: %CD%\dist\Vectorforge\Vectorforge.exe

rem ---- optional installer (needs Inno Setup 6) ----------------------------------------
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if defined ISCC (
  echo  Building installer with Inno Setup...
  "%ISCC%" packaging\installer.iss || goto :fail
  echo.
  echo  Installer built: %CD%\dist\VectorforgeSetup.exe
) else (
  echo.
  echo  To also get a one-file installer ^(VectorforgeSetup.exe^), install Inno Setup 6
  echo  from https://jrsoftware.org/isdl.php and run this file again.
)

echo.
echo  Done. Double-click dist\Vectorforge\Vectorforge.exe to start the app.
echo.
pause
exit /b 0

:fail
echo.
echo  The build failed. Scroll up to see the first error message.
echo.
pause
exit /b 1
