; Inno Setup 6 script: wraps dist\Vectorforge into dist\VectorforgeSetup.exe
; Compile with: ISCC packaging\installer.iss   (build_windows.bat does this)

#define AppName "Vectorforge"
#define AppVersion "1.0.0"

[Setup]
AppId={{6F1B7E2C-4C3A-4F55-9C1B-0D5E8A7A2F11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Vectorforge
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=VectorforgeSetup
SetupIconFile=vectorforge.ico
UninstallDisplayIcon={app}\Vectorforge.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\Vectorforge\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Vectorforge.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Vectorforge.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Vectorforge.exe"; Description: "Start {#AppName} now"; Flags: nowait postinstall skipifsilent
