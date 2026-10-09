; The installer, compiled by build.py:
;   ISCC /DAppName=... /DAppVersion=... /DSite=... /DSourceDir=... /DOutputDir=... /DTouchDate=... /DTouchTime=... installer.iss
;
; Per user, so no admin prompt. A Start-menu shortcut and an uninstaller. The WebView2 runtime if this PC has none.
; Run by the app for an update as  MFDInvoice-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART  : it then opens
; nothing itself, the app's updater starts the new version and watches it (client/src/client/hands/update.py).
; Unsigned: no signing step, and nothing here expects a certificate.
;
; Uninstalling removes the program, its updater's folder and a browser we downloaded ourselves. An interactive
; uninstall first asks whether to remove all the person's data on this PC too (months, invoices, vault, signature:
; all of %LOCALAPPDATA%\MFDInvoice\). Ticked, they must type DELETE ALL before Uninstall is enabled; it cannot be
; undone. Unticked (the default), and always in a silent uninstall, their data stays.

[Setup]
AppId={{6C0B6E5B-7D0E-4C63-9E0B-3D1B6B8B4E21}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
AppPublisherURL={#Site}
AppSupportURL={#Site}/support
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename={#AppName}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icon.ico
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppName}.exe
VersionInfoVersion={#AppVersion}
CloseApplications=yes
RestartApplications=no
; the same commit gives the same file: every file inside carries the commit's time, not the build's
TimeStampsInUTC=yes
TouchDate={#TouchDate}
TouchTime={#TouchTime}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"

[InstallDelete]
; an update replaces the program whole: no file of the version before is left beside the new one
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs touch

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\{#AppName}\update"
Type: filesandordirs; Name: "{localappdata}\{#AppName}\browser"

[Code]
const
  WebView2Key = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2Url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

function HasVersion(const Root: Integer; const Key: String): Boolean;
var
  V: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', V) and (V <> '') and (V <> '0.0.0.0');
end;

{ The window is drawn by Microsoft's WebView2 runtime. Windows 11 has it; most Windows 10 PCs do. }
function HasWebView2: Boolean;
begin
  Result := HasVersion(HKLM, 'SOFTWARE\WOW6432Node\' + WebView2Key)
         or HasVersion(HKLM, 'SOFTWARE\' + WebView2Key)
         or HasVersion(HKCU, 'Software\' + WebView2Key);
end;

{ Missing: Microsoft's own small installer is downloaded and run for this user, with no prompt. If that fails the
  install still finishes, and says what to do: the app cannot open its window without it. }
procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
begin
  if (CurStep <> ssPostInstall) or HasWebView2 then
    Exit;
  WizardForm.StatusLabel.Caption := 'Getting a Windows component the software needs (Microsoft Edge WebView2)...';
  try
    DownloadTemporaryFile(WebView2Url, 'MicrosoftEdgeWebview2Setup.exe', '', nil);
    Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE,
         ewWaitUntilTerminated, Code);
  except
    Log('WebView2 was not downloaded: ' + GetExceptionMessage);
  end;
  if not HasWebView2 then
    SuppressibleMsgBox('{#AppName} needs Microsoft Edge WebView2, and it could not be installed just now.' + #13#10 +
      'Check your internet connection and run this installer again.', mbError, MB_OK, IDOK);
end;

{ ---- uninstall ---- }
var
  DeleteData: Boolean;
  UnCheck: TNewCheckBox;
  UnEdit: TNewEdit;
  UnOk: TNewButton;

procedure UnRefresh;
begin
  UnEdit.Enabled := UnCheck.Checked;
  UnOk.Enabled := (not UnCheck.Checked) or (UnEdit.Text = 'DELETE ALL');
end;

procedure UnCheckClick(Sender: TObject);
begin
  UnRefresh;
end;

procedure UnEditChange(Sender: TObject);
begin
  UnRefresh;
end;

function InitializeUninstall: Boolean;
var
  F: TSetupForm;
  Msg, Prompt: TNewStaticText;
  Cancel: TNewButton;
begin
  Result := True;
  DeleteData := False;
  if UninstallSilent then
    Exit;
  F := CreateCustomForm(ScaleX(420), ScaleY(230), False, True);
  try
    F.Caption := 'Uninstall {#AppName}';
    Msg := TNewStaticText.Create(F);
    Msg.Parent := F;
    Msg.Left := ScaleX(16);
    Msg.Top := ScaleY(16);
    Msg.Caption := 'Remove {#AppName} from this PC.';
    UnCheck := TNewCheckBox.Create(F);
    UnCheck.Parent := F;
    UnCheck.Left := ScaleX(16);
    UnCheck.Top := ScaleY(48);
    UnCheck.Width := F.ClientWidth - ScaleX(32);
    UnCheck.Height := ScaleY(36);
    UnCheck.Caption := 'Also delete all my data on this PC: invoices, months, saved logins and signature. This can''t be undone.';
    UnCheck.OnClick := @UnCheckClick;
    Prompt := TNewStaticText.Create(F);
    Prompt.Parent := F;
    Prompt.Left := ScaleX(32);
    Prompt.Top := ScaleY(104);
    Prompt.Caption := 'Type DELETE ALL to confirm';
    UnEdit := TNewEdit.Create(F);
    UnEdit.Parent := F;
    UnEdit.Left := ScaleX(32);
    UnEdit.Top := ScaleY(124);
    UnEdit.Width := ScaleX(200);
    UnEdit.OnChange := @UnEditChange;
    UnOk := TNewButton.Create(F);
    UnOk.Parent := F;
    UnOk.Caption := 'Uninstall';
    UnOk.ModalResult := mrOk;
    UnOk.Default := True;
    UnOk.Width := ScaleX(90);
    UnOk.Height := ScaleY(26);
    UnOk.Left := F.ClientWidth - ScaleX(200);
    UnOk.Top := F.ClientHeight - ScaleY(42);
    Cancel := TNewButton.Create(F);
    Cancel.Parent := F;
    Cancel.Caption := 'Cancel';
    Cancel.ModalResult := mrCancel;
    Cancel.Cancel := True;
    Cancel.Width := ScaleX(90);
    Cancel.Height := ScaleY(26);
    Cancel.Left := F.ClientWidth - ScaleX(100);
    Cancel.Top := UnOk.Top;
    UnRefresh;
    if F.ShowModal = mrOk then
      DeleteData := UnCheck.Checked and (UnEdit.Text = 'DELETE ALL')
    else
      Result := False;
  finally
    F.Free;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and DeleteData then
    DelTree(ExpandConstant('{localappdata}\{#AppName}'), True, True, True);
end;
