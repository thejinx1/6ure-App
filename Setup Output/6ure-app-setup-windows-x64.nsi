Unicode true
Name "6ure™ App"
OutFile "C:\Users\alkim\OneDrive\Masaüstü\ㅤㅤㅤㅤㅤ\6ure Files\Setup Output\6ure-app-setup-1.5.3.exe"
InstallDir "$LOCALAPPDATA\Programs\6ure™ App"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "1.5.3.0"
VIAddVersionKey "ProductName" "6ure™ App"
VIAddVersionKey "CompanyName" "reyli"
VIAddVersionKey "FileDescription" "6ure™ App Setup"
VIAddVersionKey "FileVersion" "1.5.3"
VIAddVersionKey "ProductVersion" "1.5.3"
VIAddVersionKey "LegalCopyright" "reyli"

!include MUI2.nsh
!define MUI_ABORTWARNING
!define MUI_ICON "C:\Users\alkim\OneDrive\Masaüstü\ㅤㅤㅤㅤㅤ\6ure Files\Developer Files\Source Code\assets\6ure-logo.ico"
!define MUI_UNICON "C:\Users\alkim\OneDrive\Masaüstü\ㅤㅤㅤㅤㅤ\6ure Files\Developer Files\Source Code\assets\6ure-logo.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\6ure™ App.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch 6ure™ App"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  SetShellVarContext current
FunctionEnd

Function un.onInit
  SetShellVarContext current
FunctionEnd

Function CloseRunningApp
  DetailPrint "Closing running 6ure™ App windows..."
  nsExec::ExecToStack 'taskkill /IM "6ure™ App.exe" /T /F'
  Pop $0
  Pop $1
  nsExec::ExecToStack 'taskkill /IM "6ure Files.exe" /T /F'
  Pop $0
  Pop $1
  Sleep 1800
FunctionEnd

Section "6ure™ App" SEC_APP
  SectionIn RO
  Call CloseRunningApp
  SetOutPath "$INSTDIR"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\app-version.json"
  Delete "$INSTDIR\discord-presence.json"
  Delete "$INSTDIR\update-config.json"
  Delete "$INSTDIR\hlx-api-key.txt"
  Delete "$INSTDIR\hlx-api-key.db"
  File /r "C:\Users\alkim\AppData\Local\Temp\6ure-setup-staging-16368\app-files\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  Delete "$DESKTOP\6ure™ App.lnk"
  Delete "$DESKTOP\6ure Files.lnk"
  Delete "$SMPROGRAMS\6ure Files\6ure Files.lnk"
  RMDir "$SMPROGRAMS\6ure Files"
  CreateDirectory "$SMPROGRAMS\6ure™ App"
  CreateShortcut "$SMPROGRAMS\6ure™ App\6ure™ App.lnk" "$INSTDIR\6ure™ App.exe"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "DisplayName" "6ure™ App"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "DisplayVersion" "1.5.3"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "Publisher" "reyli"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "NoRepair" 1
SectionEnd

Section "Create desktop shortcut" SEC_DESKTOP
  SetOutPath "$INSTDIR"
  CreateShortcut "$DESKTOP\6ure™ App.lnk" "$INSTDIR\6ure™ App.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\6ure™ App.lnk"
  Delete "$DESKTOP\6ure Files.lnk"
  Delete "$SMPROGRAMS\6ure™ App\6ure™ App.lnk"
  Delete "$SMPROGRAMS\6ure Files\6ure Files.lnk"
  RMDir "$SMPROGRAMS\6ure™ App"
  RMDir "$SMPROGRAMS\6ure Files"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files"
  RMDir /r "$INSTDIR"
SectionEnd