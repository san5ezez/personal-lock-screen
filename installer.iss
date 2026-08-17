#define MyAppName "Personal Lock Screen"
#define MyAppVersion "1.0.0"

[Setup]
AppId={{B4BDB4B4-67CC-4F50-8D2D-6B98F9F8D8F1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\PersonalLockScreen
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer-output
OutputBaseFilename=PersonalLockScreenSetup
Compression=lzma
SolidCompression=yes
UninstallDisplayName={#MyAppName}
Uninstallable=yes

[Files]
Source: "dist\lock_screen.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\winlogon_shell.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Personal Lock Screen - uninstall"; Filename: "{uninstallexe}"

[Code]
const
  WinlogonKey = 'Software\Microsoft\Windows NT\CurrentVersion\Winlogon';
  BackupKey = 'Software\PersonalLockScreenInstaller';

var
  BackupShell: string;
  BackupPassword: string;
  PasswordPage: TInputQueryWizardPage;

function InitializeSetup(): Boolean;
begin
  Result := MsgBox(
    'This installer replaces Explorer for the current Windows user until the lock screen is unlocked.' + #13#10 +
    'Use only on your own PC. The uninstaller restores the previous shell.',
    mbConfirmation, MB_OKCANCEL) = IDOK;
end;

procedure InitializeWizard;
begin
  PasswordPage := CreateInputQueryPage(wpSelectDir, 'Резервный пароль',
    'Задайте пароль для разблокировки',
    'Этот пароль будет доступен только текущему пользователю Windows.');
  PasswordPage.Add('Резервный пароль:', True);
  PasswordPage.Add('Повторите пароль:', True);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = PasswordPage.ID then begin
    if (PasswordPage.Values[0] = '') or (PasswordPage.Values[0] <> PasswordPage.Values[1]) then begin
      MsgBox('Пароли должны совпадать и не быть пустыми.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then begin
    if RegQueryStringValue(HKCU, WinlogonKey, 'Shell', BackupShell) then
      RegWriteStringValue(HKCU, BackupKey, 'PreviousShell', BackupShell)
    else
      RegDeleteValue(HKCU, BackupKey, 'PreviousShell');
    if RegQueryStringValue(HKCU, 'Environment', 'PERSONAL_LOCK_PASSWORD', BackupPassword) then
      RegWriteStringValue(HKCU, BackupKey, 'PreviousPassword', BackupPassword)
    else
      RegDeleteValue(HKCU, BackupKey, 'PreviousPassword');
    RegWriteStringValue(HKCU, WinlogonKey, 'Shell', ExpandConstant('{app}\winlogon_shell.exe'));
    RegWriteStringValue(HKCU, 'Environment', 'PERSONAL_LOCK_PASSWORD', PasswordPage.Values[0]);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  SavedShell: string;
  SavedPassword: string;
begin
  if CurUninstallStep = usUninstall then begin
    if RegQueryStringValue(HKCU, BackupKey, 'PreviousShell', SavedShell) then begin
      if SavedShell <> '' then
        RegWriteStringValue(HKCU, WinlogonKey, 'Shell', SavedShell)
      else
        RegDeleteValue(HKCU, WinlogonKey, 'Shell');
    end else
      RegDeleteValue(HKCU, WinlogonKey, 'Shell');
    if RegQueryStringValue(HKCU, BackupKey, 'PreviousPassword', SavedPassword) then
      RegWriteStringValue(HKCU, 'Environment', 'PERSONAL_LOCK_PASSWORD', SavedPassword)
    else
      RegDeleteValue(HKCU, 'Environment', 'PERSONAL_LOCK_PASSWORD');
    RegDeleteKeyIncludingSubkeys(HKCU, BackupKey);
  end;
end;
