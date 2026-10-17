; Koha.Nexus Windows installer (Inno Setup 6, for the Microsoft Store
; unpackaged Win32 submission and for direct download).
;
; Build: ISCC.exe windows\setup\koha-nexus.iss  (run from the repository root
; or with the paths below; they are relative to this file)
;
; Silent install, for the Store "Installer parameters" field:
;   /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
;
; The exit codes are Windows system error codes, each one distinct, listed in
; [Code] below. Inno Setup itself does not return them: this script sets them
; with ExitProcess, and only for the scenarios it can detect.
; Plain Inno exit codes that it may still return are not in this table.

#define AppName "Koha.Nexus"
#define AppVersion "1.5.76"
#define AppPublisher "Paulo F. Baldi FH"
#define AppExe "KohaEasy.ps1"

[Setup]
AppId={{411B5332-126F-4CB4-AA31-F2F8434F69F0}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://koha.nexus
AppSupportURL=https://koha.nexus
DefaultDirName={autopf}\Koha.Nexus
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
DisableFinishedPage=yes
DisableWelcomePage=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=KohaNexus-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\windows\koha.ico
SetupIconFile=..\koha.ico
CloseApplications=no
RestartIfNeededByRun=no
AllowNoIcons=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
; The same layout install.ps1 expects: installer, installer.sha256, windows\.
Source: "..\..\installer"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\installer.sha256"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\windows\*"; DestDir: "{app}\windows"; Excludes: "setup\*"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "KohaNexus.Preflight.ps1"; DestDir: "{app}\setup"; Flags: ignoreversion

[Code]
const
  // Exit codes this script can set. Each one is a Windows system error code,
  // and no two share a value.
  ExitSuccess         = 0;     // installation successful
  ExitDiskFull        = 112;   // ERROR_DISK_FULL: not enough free space
  ExitCancelled       = 1223;  // ERROR_CANCELLED: cancelled by the user
  ExitInstallFailure  = 1603;  // ERROR_INSTALL_FAILURE: the install step failed
  ExitAlreadyRunning  = 1618;  // ERROR_INSTALL_ALREADY_RUNNING: another install is running
  ExitNetwork         = 12029; // ERROR_INTERNET_CANNOT_CONNECT: download host unreachable
  ExitPackageRejected = 1625;  // ERROR_INSTALL_PACKAGE_REJECTED: payload fails its SHA-256

  // Free space the install needs on the drive it goes to. Chosen for Debian
  // in WSL 2 plus Koha; confirm against a real install before submission.
  RequiredFreeMB = 10240;

  ERROR_ALREADY_EXISTS = 183;

var
  InstallMutex: THandle;

function CreateMutexW(lpMutexAttributes: Longint; bInitialOwner: Boolean; lpName: String): THandle;
  external 'CreateMutexW@kernel32.dll stdcall';
function GetLastError: Cardinal;
  external 'GetLastError@kernel32.dll stdcall';
procedure ExitProcess(uExitCode: Cardinal);
  external 'ExitProcess@kernel32.dll stdcall';
function SetEnvironmentVariableW(lpName, lpValue: String): Boolean;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

function InitializeSetup(): Boolean;
var
  Free, Total: Int64;
begin
  Result := True;

  // Another installer already running: stop before anything is copied.
  // Our own mutex, not Inno's SetupMutex, so no Inno message box can appear.
  InstallMutex := CreateMutexW(0, True, 'KohaNexusSetupRunning');
  if GetLastError() = ERROR_ALREADY_EXISTS then
    ExitProcess(ExitAlreadyRunning);

  // Not enough room on the install drive.
  if GetSpaceOnDisk64(ExpandConstant('{autopf}'), Free, Total) then
    if Free < Int64(RequiredFreeMB) * 1048576 then
      ExitProcess(ExitDiskFull);
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  // Cancel is only reachable on the progress page, where no confirmation
  // box is wanted: exit with the cancelled code at once.
  Confirm := False;
  ExitProcess(ExitCancelled);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Params: String;
begin
  if CurStep <> ssPostInstall then
    Exit;

  // Payload check (SHA-256 of installer) and network reachability.
  // Prints nothing; its exit code is one of the constants above, or 1 for a
  // script error, which maps to ExitInstallFailure.
  Params := '-NoProfile -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\setup\KohaNexus.Preflight.ps1') + '" -AppDir "' +
    ExpandConstant('{app}') + '"';
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    ExitProcess(ExitInstallFailure);
  if ResultCode = ExitPackageRejected then ExitProcess(ExitPackageRejected);
  if ResultCode = ExitNetwork then ExitProcess(ExitNetwork);
  if ResultCode <> 0 then ExitProcess(ExitInstallFailure);

  // The install itself: the same entry point as the PowerShell one-liner.
  SetEnvironmentVariableW('KOHAEASY_SOURCE', ExpandConstant('{app}'));
  Params := '-NoProfile -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\windows\{#AppExe}') + '" Install';
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    ExitProcess(ExitInstallFailure);
  // KohaEasy.ps1 returns 0 on success and 1 on any step failure (the user
  // runs the installer again to continue from that step).
  if ResultCode <> 0 then ExitProcess(ExitInstallFailure);
end;
