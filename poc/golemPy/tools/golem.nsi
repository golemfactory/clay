!define MULTIUSER_EXECUTIONLEVEL Highest
!define MULTIUSER_MUI
!define MULTIUSER_INSTALLMODE_COMMANDLINE
!define MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_KEY "Software\Golem"
!define MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_VALUENAME ""
!define MULTIUSER_INSTALLMODE_INSTDIR "Golem"
!include x64.nsh
!include "winmessages.nsh"
!include MultiUser.nsh
!include "MUI2.nsh"


Name "Golem"

OutFile "Installer.exe"


Var "INSTGOLEM"

!define MUI_ABORTWARNING
!define UNINST_KEY \
	  "Software\Microsoft\Windows\CurrentVersion\Uninstall\Golem"

Function .onInit
	!insertmacro MULTIUSER_INIT

FunctionEnd

Function un.onInit
  !insertmacro MULTIUSER_UNINIT
FunctionEnd

InstallDirRegKey HKCU "Software\Golem" ""

!insertmacro MUI_PAGE_WELCOME
!insertmacro MULTIUSER_PAGE_INSTALLMODE
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

	${If} $MultiUser.InstallMode == "AllUsers"
		AccessControl::GrantOnFile "$INSTDIR" "(BU)" "FullAccess"
	${EndIf}

;	AccessControl::GrantOnFile "$INSTDIR\src\examples\gnr\node_data" "(BU)" "FullAccess"
;	AccessControl::GrantOnFile "$INSTDIR\src\save" "(BU)" "FullAccess"
;	AccessControl::GrantOnFile "$INSTDIR\temp.bat" "(BU)" "FullAccess"

	WriteRegStr SHCTX "${UNINST_KEY}" "DisplayName" "Golem"
	WriteRegStr SHCTX "${UNINST_KEY}" "UninstallString" \
    "$\"$INSTDIR\uninstaller.exe$\" /$MultiUser.InstallMode"
	WriteRegStr SHCTX "${UNINST_KEY}" "QuietUninstallString" \
    "$\"$INSTDIR\uninstaller.exe$\" /$MultiUser.InstallMode /S"



	StrCpy $INSTGOLEM "$INSTDIR\src"

   !define env_hklm 'HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"'
   !define env_hkcu 'HKCU "Environment"'



	${If} $MultiUser.InstallMode == "AllUsers"
		WriteRegExpandStr ${env_hklm} GOLEM $INSTGOLEM
	${Else}
		WriteRegExpandStr ${env_hkcu} GOLEM $INSTGOLEM
	${EndIf}



   SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

    CreateDirectory "$SMPROGRAMS\golem"
	CreateShortCut "$SMPROGRAMS\golem\Uninstall.lnk"  "$INSTDIR\uninstaller.exe"
	CreateShortCut "$SMPROGRAMS\golem\golem.lnk" "$INSTDIR\golem.exe"

	!define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_KEY "${MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_KEY}"
	!define MULTIUSER_INSTALLMODE_DEFAULT_REGISTRY_VALUENAME "${MULTIUSER_INSTALLMODE_INSTDIR_REGISTRY_VALUENAME}"

	WriteUninstaller $INSTDIR\uninstaller.exe

SectionEnd

Section "Uninstall"

	${If} $MultiUser.InstallMode == "AllUsers"
		DeleteRegValue ${env_hklm} GOLEM
		DeleteRegValue ${env_hkcu} GOLEM
	${Else}
		DeleteRegValue ${env_hkcu} GOLEM
	${EndIf}
	SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000


	Delete $INSTDIR\uninstaller.exe

	RmDir /r $INSTDIR\src
	RmDir /r $INSTDIR\Python27
	Delete $INSTDIR\golem.exe
	Delete $INSTDIR\temp.bat

	Delete "$SMPROGRAMS\golem\*.*"
	RMDir "$SMPROGRAMS\golem"

	RmDir $INSTDIR

	DeleteRegKey SHCTX "${UNINST_KEY}"

SectionEnd