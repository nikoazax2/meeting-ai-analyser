; Meeting AI Analyser - Inno Setup script
; Builds dist\MeetingAIAnalyser-Setup.exe

#define AppName "Meeting AI Analyser"
#define AppPublisher "Neoteem"
#define AppExeName "MeetingAIAnalyser.exe"
#define AppId "{{B7E3F9C2-5A4E-4F8D-9C1A-MEETINGAIANALYS}"

#ifndef AppVersion
  #define AppVersion "1.1.2"
#endif

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\MeetingAIAnalyser
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=MeetingAIAnalyser-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
CloseApplications=yes
RestartApplications=yes
; Silent install during auto-update: /SILENT /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "dist\MeetingAIAnalyser.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  // In silent mode (auto-update), relaunch the app after install
  if (CurStep = ssDone) and WizardSilent() then
    Exec(ExpandConstant('{app}\{#AppExeName}'), '', '', SW_SHOW, ewNoWait, ResultCode);
end;
