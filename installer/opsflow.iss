; Inno Setup script for the OpsFlow desktop client (Fase 10).
;
; Packages the PyInstaller output (dist/OpsFlow/, built first via
; `installer/OpsFlow.spec`) into a real Windows installer: Start Menu
; shortcut, optional desktop shortcut, proper uninstaller registered with
; Windows. Build with:
;
;     "C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer\opsflow.iss
;
; (or wherever Inno Setup 6 installed ISCC.exe on your machine — installed
; via `winget install JRSoftware.InnoSetup`). Output:
; installer\OpsFlow-Setup-<version>.exe — never committed (see .gitignore).
;
; Requires `dist\OpsFlow\OpsFlow.exe` to already exist — run PyInstaller
; first (`pyinstaller installer\OpsFlow.spec` from the repo root).

#define MyAppName "OpsFlow"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "OpsFlow"
#define MyAppExeName "OpsFlow.exe"

[Setup]
; Gerado uma única vez para este produto — nunca mude entre versões, é o
; que permite ao Windows saber que uma instalação nova é uma ATUALIZAÇÃO
; da anterior, não um programa diferente.
AppId={{6E9B6E6E-6E6F-4F70-9F6C-4F1B6C6F6F6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=OpsFlow-Setup-{#MyAppVersion}
SetupIconFile=assets\opsflow.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
Source: "..\dist\OpsFlow\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o {#MyAppName} agora"; Flags: nowait postinstall skipifsilent
