!include x64.nsh
!include "winmessages.nsh"
!include "MUI2.nsh"

	Name "Golem"

	OutFile "Installer.exe"
   
	RequestExecutionLevel user
	RequestExecutionLevel admin
 
	Var "INSTGOLEM"
	
	!define MUI_ABORTWARNING
 
Function .onInit
	${If} ${RunningX64}
		StrCpy $INSTDIR "$PROGRAMFILES64\golem"
	${Else}
		StrCpy $INSTDIR "$PROGRAMFILES\golem"
	${EndIf}     
FunctionEnd

InstallDirRegKey HKCU "Software\Golem" ""

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY

!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH


!insertmacro MUI_LANGUAGE "English"

Section "Install Golem" SecGolem

	SectionIn RO
  
	CreateDirectory $INSTDIR

	SetOutPath $INSTDIR
	
	File /nonfatal /a /r "golem\"	
	
	AccessControl::GrantOnFile "$INSTDIR" "(BU)" "FullAccess"
	;AccessControl::GrantOnFile "$INSTDIR\src\examples\gnr\node_data" "(BU)" "FullAccess"
;	AccessControl::GrantOnFile "$INSTDIR\src\save" "(BU)" "FullAccess"
;	AccessControl::GrantOnFile "$INSTDIR\temp.bat" "(BU)" "FullAccess"

	WriteUninstaller $INSTDIR\uninstaller.exe

	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Golem" \
                 "DisplayName" "Golem"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Golem" \
                 "UninstallString" "$\"$INSTDIR\uninstaller.exe$\""

	StrCpy $INSTGOLEM "$INSTDIR\src"

   !define env_hklm 'HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"'
   !define env_hkcu 'HKCU "Environment"'
   WriteRegExpandStr ${env_hklm} GOLEM $INSTGOLEM
   SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
    
    CreateDirectory "$SMPROGRAMS\golem"
	CreateShortCut "$SMPROGRAMS\golem\Uninstall.lnk" "$INSTDIR\uninstaller.exe"
	CreateShortCut "$SMPROGRAMS\golem\golem.lnk" "$INSTDIR\golem.exe"
 

SectionEnd

Section "Uninstall"


	DeleteRegValue ${env_hklm} GOLEM
	DeleteRegValue ${env_hkcu} GOLEM
	SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Golem"

	Delete $INSTDIR\uninstaller.exe

	RmDir /r $INSTDIR\src
	RmDir /r $INSTDIR\Python27
	Delete $INSTDIR\golem.exe
	Delete $INSTDIR\temp.bat
    
	Delete "$SMPROGRAMS\golem\*.*"
	RMDir "$SMPROGRAMS\golem"
	
	RmDir $INSTDIR

SectionEnd