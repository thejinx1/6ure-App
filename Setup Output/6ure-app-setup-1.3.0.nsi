Unicode true
Name "6ure™ App"
OutFile "C:\Users\alkim\OneDrive\Masaüstü\6ure Files\Setup Output\6ure-app-setup-1.3.0.exe"
InstallDir "$LOCALAPPDATA\Programs\6ure™ App"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "1.3.0.0"
VIAddVersionKey "ProductName" "6ure™ App"
VIAddVersionKey "CompanyName" "reyli"
VIAddVersionKey "FileDescription" "6ure™ App Setup"
VIAddVersionKey "FileVersion" "1.3.0"
VIAddVersionKey "ProductVersion" "1.3.0"
VIAddVersionKey "LegalCopyright" "reyli"

!include MUI2.nsh
!define MUI_ABORTWARNING
!define MUI_ICON "C:\Users\alkim\OneDrive\Masaüstü\6ure Files\Developer Files\Source Code\assets\6ure-logo.ico"
!define MUI_UNICON "C:\Users\alkim\OneDrive\Masaüstü\6ure Files\Developer Files\Source Code\assets\6ure-logo.ico"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "C:\Users\alkim\OneDrive\Masaüstü\6ure Files\Setup Output\staging\6ure™ App\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  Delete "$DESKTOP\6ure Files.lnk"
  Delete "$SMPROGRAMS\6ure Files\6ure Files.lnk"
  RMDir "$SMPROGRAMS\6ure Files"
  CreateDirectory "$SMPROGRAMS\6ure™ App"
  CreateShortcut "$SMPROGRAMS\6ure™ App\6ure™ App.lnk" "$INSTDIR\6ure™ App.exe"
  CreateShortcut "$DESKTOP\6ure™ App.lnk" "$INSTDIR\6ure™ App.exe"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "DisplayName" "6ure™ App"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "DisplayVersion" "1.3.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "Publisher" "reyli"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure™ App" "NoRepair" 1
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
