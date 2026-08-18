#define MyAppName "Personal Lock Screen"
#define MyAppVersion "1.1.1"

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
  LanguagePage: TInputOptionWizardPage;
  PasswordPage: TInputQueryWizardPage;

function InitializeSetup(): Boolean;
begin
  Result := MsgBox(
    'This installer replaces Explorer for the current Windows user until the lock screen is unlocked.' + #13#10 +
    'Установщик заменяет Explorer для текущего пользователя до разблокировки.',
    mbConfirmation, MB_OKCANCEL) = IDOK;
end;

procedure InitializeWizard;
begin
  LanguagePage := CreateInputOptionPage(wpSelectDir,
    'Language / Язык',
    'Choose the application language / Выберите язык',
    'This affects the lock screen and Telegram messages. / Это влияет на экран и сообщения бота.',
    True, False);
  LanguagePage.Add('Русский');
  LanguagePage.Add('English');
  LanguagePage.SelectedValueIndex := 0;

  PasswordPage := CreateInputQueryPage(LanguagePage.ID,
    'Backup password / Резервный пароль',
    'Set a backup password / Задайте резервный пароль',
    'The password is used to unlock the screen if Telegram is unavailable. / Пароль нужен для разблокировки при недоступном Telegram.');
  PasswordPage.Add('Backup password / Резервный пароль:', True);
  PasswordPage.Add('Repeat password / Повторите пароль:', True);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = PasswordPage.ID then begin
    if (PasswordPage.Values[0] = '') or (PasswordPage.Values[0] <> PasswordPage.Values[1]) then begin
      MsgBox('Passwords must match and cannot be empty. / Пароли должны совпадать и не быть пустыми.', mbError, MB_OK);
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
    RegWriteStringValue(HKCU, WinlogonKey, 'Shell', ExpandConstant('{app}\winlogon_shell.exe'));
    RegWriteStringValue(HKCU, 'Environment', 'PERSONAL_LOCK_PASSWORD', PasswordPage.Values[0]);
    if LanguagePage.SelectedValueIndex = 1 then
      RegWriteStringValue(HKCU, 'Environment', 'PERSONAL_LOCK_LANGUAGE', 'en')
    else
      RegWriteStringValue(HKCU, 'Environment', 'PERSONAL_LOCK_LANGUAGE', 'ru');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  SavedShell: string;
begin
  if CurUninstallStep = usUninstall then begin
    if RegQueryStringValue(HKCU, BackupKey, 'PreviousShell', SavedShell) then begin
      if SavedShell <> '' then
        RegWriteStringValue(HKCU, WinlogonKey, 'Shell', SavedShell)
      else
        RegDeleteValue(HKCU, WinlogonKey, 'Shell');
    end else
      RegDeleteValue(HKCU, WinlogonKey, 'Shell');
    RegDeleteValue(HKCU, 'Environment', 'PERSONAL_LOCK_PASSWORD');
    RegDeleteValue(HKCU, 'Environment', 'PERSONAL_LOCK_LANGUAGE');
    RegDeleteKeyIncludingSubkeys(HKCU, BackupKey);
  end;
end;
