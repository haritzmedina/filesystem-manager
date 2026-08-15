; ============================================================================
;  Instalador / desinstalador de Filesystem Manager (filesysman)
;  Windows, Inno Setup 6.2+
;  Compilar con:  iscc installer_win.iss   (o abrir el archivo en el IDE de Inno)
;
;  Requiere haber ejecutado antes:  python build.py
;  (genera dist\filesysman\  y  dist\filesysman-gui.exe)
;
;  El instalador:
;    - Instala en %ProgramFiles%\FilesystemManager
;    - Crea accesos directos en el Menu de Inicio y en el Escritorio
;    - Agrega el directorio de instalacion al PATH del sistema (HKLM)
;    - Registra un desinstalador nativo en "Agregar o quitar programas"
;      y lo elimina del PATH al desinstalar
; ============================================================================

#define MyAppName "Filesystem Manager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Filesystem Manager Project"
#define MyAppExeName "filesysman-gui.exe"
#define MyAppCliName "filesysman.exe"

[Setup]
AppId={{6F9E2B81-4C7A-4F5D-9A3E-1B8C0D2E5F7A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\FilesystemManager
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=Filesysman_Setup
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription=Analizador de espacio en disco (CLI + GUI)
#ifexist "assets\app.ico"
SetupIconFile=assets\app.ico
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\filesysman\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\filesysman-gui.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{#MyAppName} (CLI)"; Filename: "{app}\{#MyAppCliName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; Agrega el directorio de instalacion al PATH del sistema (si aun no esta).
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath('{app}')

[Code]
const
  EnvironmentKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

function NeedsAddPath(Param: string): Boolean;
var
  OrigPath: string;
begin
  Result := True;
  if RegQueryStringValue(HKEY_LOCAL_MACHINE, EnvironmentKey, 'Path', OrigPath) then
  begin
    Result := Pos(';' + Uppercase(Param) + ';', ';' + Uppercase(OrigPath) + ';') = 0;
  end;
end;

procedure RemoveFromPath(InstalledPath: string);
var
  OrigPath, Remainder, Segment, NewPath: string;
  P: Integer;
begin
  NewPath := '';
  if RegQueryStringValue(HKEY_LOCAL_MACHINE, EnvironmentKey, 'Path', OrigPath) then
  begin
    Remainder := OrigPath;
    repeat
      P := Pos(';', Remainder);
      if P > 0 then
      begin
        Segment := Trim(Copy(Remainder, 1, P - 1));
        Remainder := Copy(Remainder, P + 1, Length(Remainder));
      end
      else
      begin
        Segment := Trim(Remainder);
        Remainder := '';
      end;
      if (Segment <> '') and (CompareText(Segment, InstalledPath) <> 0) then
        NewPath := NewPath + Segment + ';';
    until Remainder = '';
    RegWriteExpandStringValue(HKEY_LOCAL_MACHINE, EnvironmentKey, 'Path', NewPath);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveFromPath(ExpandConstant('{app}'));
end;
