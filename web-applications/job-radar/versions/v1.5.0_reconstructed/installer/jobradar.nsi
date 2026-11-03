; Job Radar – Windows installer (built with NSIS)
; Installs for the current user only (no admin rights needed), installs Python if it's missing,
; and adds Desktop / Start menu shortcuts.

Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"

!define APPNAME "Job Radar"
!define APPVER "1.5.0"
!define PYVER "3.12.7"
!define PYURL "https://www.python.org/ftp/python/${PYVER}/python-${PYVER}-amd64.exe"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\JobRadar"

Name "${APPNAME}"
OutFile "..\..\JobRadar-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\JobRadar"
InstallDirRegKey HKCU "Software\JobRadar" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "${APPNAME} ${APPVER}"
VIProductVersion "${APPVER}.0"
VIAddVersionKey "ProductName" "${APPNAME}"
VIAddVersionKey "FileDescription" "${APPNAME} installer"
VIAddVersionKey "FileVersion" "${APPVER}"
VIAddVersionKey "LegalCopyright" "Blive Co"

!define MUI_ICON "..\jobradar.ico"
!define MUI_UNICON "..\jobradar.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Install ${APPNAME}"
!define MUI_WELCOMEPAGE_TEXT "${APPNAME} finds new jobs that match a description, checks they're still open, and emails the best matches with direct apply links.$\r$\n$\r$\nIt runs on this computer. If Python isn't installed yet, setup will offer to download it from python.org (about 25 MB).$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Start ${APPNAME} now"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Var PyOk

Function CheckPython
  StrCpy $PyOk "0"
  nsExec::ExecToStack 'cmd /c py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"'
  Pop $0
  Pop $1
  ${If} $0 == "0"
    StrCpy $PyOk "1"
    Return
  ${EndIf}
  nsExec::ExecToStack 'cmd /c python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"'
  Pop $0
  Pop $1
  ${If} $0 == "0"
    StrCpy $PyOk "1"
    Return
  ${EndIf}
  ${If} ${FileExists} "$LOCALAPPDATA\Programs\Python\Launcher\py.exe"
    StrCpy $PyOk "1"
  ${EndIf}
FunctionEnd

Function LaunchApp
  ExecShell "open" "$INSTDIR\Start Job Radar.bat" "" SW_SHOWNORMAL
FunctionEnd

Section "Job Radar" SecMain
  SetOutPath "$INSTDIR"
  ; app files (your searches, settings and results in data\ and config\settings.json are kept on upgrade)
  File /r /x "__pycache__" /x "tests" /x "installer" /x "data" /x "reports" /x "settings.json" /x "secrets.json" /x "*.pyc" "..\*.*"

  DetailPrint "Checking for Python 3.9 or newer..."
  Call CheckPython
  ${If} $PyOk != "1"
    MessageBox MB_YESNO|MB_ICONQUESTION "${APPNAME} needs Python 3.9 or newer, which isn't installed.$\r$\n$\r$\nDownload and install Python ${PYVER} from python.org now? (about 25 MB, installs for your user only)" IDYES getpy
      MessageBox MB_OK|MB_ICONINFORMATION "${APPNAME} is installed, but won't start until Python is installed.$\r$\nGet it from https://www.python.org/downloads/ and tick 'Add python.exe to PATH'."
      Goto pydone
    getpy:
      DetailPrint "Downloading Python ${PYVER} from python.org..."
      nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri ${PYURL} -OutFile $\"$TEMP\python-${PYVER}-amd64.exe$\""'
      Pop $0
      ${IfNot} ${FileExists} "$TEMP\python-${PYVER}-amd64.exe"
        MessageBox MB_OK|MB_ICONEXCLAMATION "Couldn't download Python (check the internet connection).$\r$\nInstall it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then start ${APPNAME}."
        Goto pydone
      ${EndIf}
      DetailPrint "Installing Python ${PYVER} (this takes a minute)..."
      ExecWait '"$TEMP\python-${PYVER}-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_test=0 Shortcuts=0' $0
      Delete "$TEMP\python-${PYVER}-amd64.exe"
      ${If} $0 != "0"
        MessageBox MB_OK|MB_ICONEXCLAMATION "The Python installer stopped with code $0.$\r$\nInstall it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then start ${APPNAME}."
      ${Else}
        DetailPrint "Python installed."
      ${EndIf}
  ${Else}
    DetailPrint "Python found."
  ${EndIf}
  pydone:

  ; shortcuts
  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\Start Job Radar.bat" "" "$INSTDIR\jobradar.ico" 0 SW_SHOWMINIMIZED
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Scan now.lnk" "$INSTDIR\Scan Now.bat" "" "$INSTDIR\jobradar.ico" 0
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Job Radar folder.lnk" "$INSTDIR"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\Start Job Radar.bat" "" "$INSTDIR\jobradar.ico" 0 SW_SHOWMINIMIZED

  ; uninstaller + Apps & features entry
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\JobRadar" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayVersion" "${APPVER}"
  WriteRegStr HKCU "${UNINSTKEY}" "Publisher" "Blive Co"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\jobradar.ico"
  WriteRegStr HKCU "${UNINSTKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  nsExec::ExecToLog 'schtasks /Delete /TN "JobRadar\DailyScan" /F'
  Delete "$DESKTOP\${APPNAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APPNAME}"
  MessageBox MB_YESNO|MB_ICONQUESTION "Also delete your saved searches, settings, attachments and past reports?" IDYES wipe
    RMDir /r "$INSTDIR\jobradar"
    RMDir /r "$INSTDIR\vendor"
    Delete "$INSTDIR\*.bat"
    Delete "$INSTDIR\*.sh"
    Delete "$INSTDIR\*.md"
    Delete "$INSTDIR\jobradar.ico"
    Delete "$INSTDIR\config\companies.json"
    Delete "$INSTDIR\Uninstall.exe"
    Goto regs
  wipe:
    RMDir /r "$INSTDIR"
  regs:
  DeleteRegKey HKCU "${UNINSTKEY}"
  DeleteRegKey HKCU "Software\JobRadar"
SectionEnd
