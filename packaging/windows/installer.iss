#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef PayloadDir
  #error PayloadDir is required
#endif
#ifndef OutputPath
  #error OutputPath is required
#endif
[Setup]
AppId={{D66AB702-6840-4684-8B67-77DD1BE89D04}
AppName=Cold Mailer Preview
AppVersion={#AppVersion}
AppPublisher=Cold Mailer Project
DefaultDirName={localappdata}\Programs\ColdMailerPreview
DefaultGroupName=Cold Mailer Preview
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputPath}
OutputBaseFilename=ColdMailer-{#AppVersion}-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ColdMailer.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Cold Mailer Preview"; Filename: "{app}\ColdMailer.exe"
; Profile databases and credentials are outside {app}; uninstall never deletes them.
