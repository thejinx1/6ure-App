Unicode true
Name "6ure Files"
OutFile "C:\Users\alkim\OneDrive\Masaüstü\6ure Files\Setup Output\6ure-files-setup-1.1.0.exe"
InstallDir "$LOCALAPPDATA\Programs\6ure Files"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "1.1.0.0"
VIAddVersionKey "ProductName" "6ure Files"
VIAddVersionKey "CompanyName" "reyli"
VIAddVersionKey "FileDescription" "6ure Files Setup"
VIAddVersionKey "FileVersion" "1.1.0"
VIAddVersionKey "ProductVersion" "1.1.0"
VIAddVersionKey "LegalCopyright" "reyli"

!include MUI2.nsh
!define MUI_ABORTWARNING
!define MUI_ICON "C:\Users\alkim\OneDrive\Masaüstü\6ure Files\Developer Files\Source Code\assets\6urefiles.ico"
!define MUI_UNICON "C:\Users\alkim\OneDrive\Masaüstü\6ure Files\Developer Files\Source Code\assets\6urefiles.ico"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "C:\Users\alkim\OneDrive\Masaüstü\6ure Files\Setup Output\staging\6ure Files\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\6ure Files"
  CreateShortcut "$SMPROGRAMS\6ure Files\6ure Files.lnk" "$INSTDIR\6ure Files.exe"
  CreateShortcut "$DESKTOP\6ure Files.lnk" "$INSTDIR\6ure Files.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files" "DisplayName" "6ure Files"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files" "DisplayVersion" "1.1.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files" "Publisher" "reyli"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\6ure Files.lnk"
  Delete "$SMPROGRAMS\6ure Files\6ure Files.lnk"
  RMDir "$SMPROGRAMS\6ure Files"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\6ure Files"
  RMDir /r "$INSTDIR"
SectionEnd
