; Instalador do MD Launcher (Inno Setup 6)
#define AppName "MD Launcher"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppExe "MDLauncher.exe"

[Setup]
AppId={{C2EEFC84-6CBD-4F91-99C7-3D096F44944F}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=leoblaidd
AppPublisherURL=https://github.com/leoblaidd/MDlauncher
AppSupportURL=https://github.com/leoblaidd/MDlauncher/issues
DefaultDirName={autopf}\MD Launcher
DefaultGroupName=MD Launcher
; mostra a página "Onde instalar?"
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=MDLauncher-{#AppVersion}-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\MDLauncher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\MD Launcher"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\MD Launcher"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,MD Launcher}"; Flags: nowait postinstall skipifsilent
