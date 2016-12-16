@ECHO OFF

for /f "skip=1 delims=" %%x in ('wmic cpu get addresswidth') do if not defined AddressWidth set AddressWidth=%%x

if %AddressWidth%==64 (
    SET ARCH=64
    SET IPFS_ARCH=amd64
) else (
    SET ARCH=32
    SET IPFS_ARCH=386
)

SET EXE_NAME=golemapp.exe

SET EXE_DIR=%~dp0\exe.win32-2.7
SET UTILS_DIR=%~dp0\utils
SET SCRIPTS_DIR=%~dp0\scripts
SET DOCKER_DIR=%~dp0\docker

SET UPDATE_SERVER=http://52.40.149.24:9999
SET UPDATE_URL=%UPDATE_SERVER%/golem/

SET UPDATE_FILE=win32.version
SET UPDATE_PACKAGE=golem-win32-latest.zip
SET UPDATE_PACKAGE_LOCAL=golem-win32.zip

set UPDATE_FILE_URL=%UPDATE_URL%%UPDATE_FILE%
set UPDATE_PACKAGE_URL=%UPDATE_URL%%UPDATE_PACKAGE%

set LOCAL_VERSION_FILE=.version
set REMOTE_VERSION_FILE=.version_r

SET IPFS_DIST_SRV=http://dist.ipfs.io
SET IPFS_VER=v0.4.2
SET IPFS_URL=%IPFS_DIST_SRV%/go-ipfs/%IPFS_VER%/go-ipfs_%IPFS_VER%_windows-%IPFS_ARCH%.zip
SET IPFS_DIR=go-ipfs

SET GETH_URL=http://gethstore.blob.core.windows.net/builds/geth-windows-386-1.5.4-b70acf3c.zip
SET GETH_DIR=geth

SET DOCKER_INI_FILE=%DOCKER_DIR%\images.ini

::----------------------------------------------------------------------------------------------------------------------
setlocal enabledelayedexpansion
::----------------------------------------------------------------------------------------------------------------------
:SETUP_ENV

SET lf=-
set "i="
FOR /F "delims=" %%i IN ('hostname') DO SET HOSTNAME=%%i

set "i="
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /format:list') do set datetime=%%I
set datetime=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2%_%datetime:~8,2%-%datetime:~10,2%-%datetime:~12,2%

SET PATH=%~dp0;%~dp0\%IPFS_DIR%;%~dp0\%GETH_DIR%;%PATH%
SET IPFS_PATH=%~dp0/.ipfs
SET IPFS_LOG_PATH=%~dp0/ipfs.log
SET LOG_PATH=%~dp0/golem_%HOSTNAME%_%datetime%.log

SET UPDATED_SCRIPT=%~dp0\.%~nx0
::----------------------------------------------------------------------------------------------------------------------
:CHECK_UPDATE

echo Checking for updates

cscript.exe //B "%UTILS_DIR%\download.vbs" %UPDATE_FILE_URL% "%~dp0\%REMOTE_VERSION_FILE%"

if exist %LOCAL_VERSION_FILE% (
    if exist %REMOTE_VERSION_FILE% (
        for /f %%a in (%LOCAL_VERSION_FILE%) do (
            for /f %%b in (%REMOTE_VERSION_FILE%) do (
                for /f %%n in ('cscript.exe //nologo "%UTILS_DIR%\eval.vbs" "%%b > %%a"') do (
                    if "%%n"=="-1" goto UPDATE
                )
                goto POST_CHECK_UPDATE
            )
            goto POST_CHECK_UPDATE
        )
    )
) else goto UPDATE

:POST_CHECK_UPDATE
::----------------------------------------------------------------------------------------------------------------------
:INIT_DOCKER

set DOCKER_MACHINE="%DOCKER_TOOLBOX_INSTALL_PATH%\docker-machine.exe"
set VM=%DOCKER_MACHINE_NAME%
if "%VM%"=="" (
    set VM=default
)

if "%VBOX_MSI_INSTALL_PATH%"=="" (
    set VBOXMANAGE="%VBOX_INSTALL_PATH%VBoxManage.exe"
) else (
    set VBOXMANAGE="%VBOX_MSI_INSTALL_PATH%VBoxManage.exe"
)

if not exist %DOCKER_MACHINE% (
    cscript.exe "%UTILS_DIR%\notify.vbs" "Docker Machine is not installed. Please re-run the Toolbox Installer and try again."
    goto END
)

if not exist %VBOXMANAGE% (
    cscript.exe "%UTILS_DIR%\notify.vbs" "VirtualBox is not installed. Please re-run the Toolbox Installer and try again."
    goto END
)

%VBOXMANAGE% list vms | findstr "%VM%"
if errorlevel 1 (
    set RUNNING=0
) else (
    set RUNNING=1
)

if "%RUNNING%"=="0" (
    rd /s /q "%userprofile%\.docker\machine\machines\%VM%"

    if not "%HTTP_PROXY%"=="" (
        set PROXY_ENV=%PROXY_ENV% --engine-env HTTP_PROXY=%HTTP_PROXY%
    )

    if not "%HTTPS_PROXY%"=="" (
        set PROXY_ENV=%PROXY_ENV% --engine-env HTTPS_PROXY=%HTTPS_PROXY%
    )

    if not "%NO_PROXY%"=="" (
        set PROXY_ENV=%PROXY_ENV% --engine-env NO_PROXY=%NO_PROXY%
    )

    %DOCKER_MACHINE% create -d virtualbox %PROXY_ENV% %VM%
)

set "i="
for /F "delims=" %%i in ('%DOCKER_MACHINE% status %VM%') DO SET VM_STATUS=%%i

if not "%VM_STATUS%"=="Running" (
    echo y > .yes
    %DOCKER_MACHINE% start %VM%
    %DOCKER_MACHINE% regenerate-certs %VM% < .yes
    del .yes
)

set "i="
for /F "tokens=* delims=" %%i in ('%DOCKER_MACHINE% env --shell=cmd %VM%') DO (
    %%i
) >nul 2>nul

::----------------------------------------------------------------------------------------------------------------------
:CHECK_DOCKER

if "%DOCKER_HOST%"=="" (
    cscript.exe "%UTILS_DIR%\notify.vbs" "Cannot start docker machine"
    GOTO END
)

::----------------------------------------------------------------------------------------------------------------------
:CHECK_IPFS

:: if not exist %IPFS_DIR% (
::     ECHO Downloading IPFS
::     cscript.exe //B "%UTILS_DIR%\download.vbs" "%IPFS_URL%" "%~dp0\ipfs.zip"
::     cscript.exe //B "%UTILS_DIR%\unzip.vbs" ipfs.zip
::     del ipfs.zip
:: )

:: IF not exist %IPFS_DIR% (
::     cscript.exe "%UTILS_DIR%\notify.vbs" "Error downloading IPFS"
::     GOTO END
:: )

:CHECK_GETH

if not exist %GETH_DIR% (
    ECHO Downloading Geth
    cscript.exe //B "%UTILS_DIR%\download.vbs" "%GETH_URL%" "%~dp0\geth.zip"
    cscript.exe //B "%UTILS_DIR%\unzip.vbs" geth.zip

    set "i="
    set "GETH_EX_DIR="
    for /F "delims=" %%i in ('dir /b geth-*') DO (
        set GETH_EX_DIR=%%i
        goto MOVE_GETH
    )

    :MOVE_GETH
    ren "%GETH_EX_DIR%" "%GETH_DIR%"
    del geth.zip
)

if not exist %GETH_DIR% (
    cscript.exe "%UTILS_DIR%\notify.vbs" "Error downloading geth"
    goto END
)

::----------------------------------------------------------------------------------------------------------------------
:START_IPFS

:: taskkill /im ipfs.exe /F > nul 2>&1
:: ipfs init > nul 2>&1
:: start /B ipfs daemon

::----------------------------------------------------------------------------------------------------------------------

:CHECK_IPFS

:: timeout 3 > nul

::----------------------------------------------------------------------------------------------------------------------
:BUILD_DOCKER_IMAGES

for /F "tokens=1,2,3" %%i in (%DOCKER_INI_FILE%) do call :check_docker_image %%i %%j %%k
goto POST_BUILD_DOCKER_IMAGES

:check_docker_image
    set IMG_NAME=%1
    set IMG_FILE=%2
    set IMG_TAG=%3
    set IMG=%IMG_NAME%:%IMG_TAG%

    echo Checking docker image %IMG%

    set "gi="
    for /F "delims=" %%e in ('docker images -q %IMG%') do (
        if not defined gi (
            set "gi=%%e"
        )
    )
    if "!gi!"=="" (
        echo Building image %IMG%
        cd %DOCKER_DIR%
        docker build -t %IMG_NAME% -f %IMG_FILE% . && docker tag %IMG_NAME% %IMG%
        cd %~dp0
    )
    exit /b

:POST_BUILD_DOCKER_IMAGES
::----------------------------------------------------------------------------------------------------------------------
:START_GOLEM

echo Starting Golem

type .version >> "%LOG_PATH%"

if "%*"=="" (
    "%EXE_DIR%\%EXE_NAME%" --gui >> "%LOG_PATH%" 2>&1
) else (
    "%EXE_DIR%\%EXE_NAME%" %* >> "%LOG_PATH%" 2>&1
)

::----------------------------------------------------------------------------------------------------------------------
:STOP_IPFS
:: taskkill /im ipfs.exe /F

::----------------------------------------------------------------------------------------------------------------------

if exist "%UPDATED_SCRIPT%" del /q "%UPDATED_SCRIPT%"
goto END

::----------------------------------------------------------------------------------------------------------------------
:UPDATE

echo Updating Golem

if exist "%~dp0\%UPDATE_PACKAGE_LOCAL%" del /q "%~dp0\%UPDATE_PACKAGE_LOCAL%" >nul 2>nul

cscript.exe //B "%UTILS_DIR%\download.vbs" %UPDATE_PACKAGE_URL% "%~dp0\%UPDATE_PACKAGE_LOCAL%"
if not exist "%~dp0\%UPDATE_PACKAGE_LOCAL%" (
    cscript.exe "%UTILS_DIR%\notify.vbs" "Error downloading update. Please try again."
    goto END
)

if exist "%EXE_DIR%" rd /S /Q "%EXE_DIR%"
if exist "%SCRIPTS_DIR%" rd /S /Q "%SCRIPTS_DIR%"
if exist "%DOCKER_DIR%" rd /S /Q "%DOCKER_DIR%"
if exist "%~dp0\golem" rd /S /Q "%~dp0\golem"
if exist "%~dp0\.version" del /q "%~dp0\.version"

cscript.exe //B "%UTILS_DIR%\unzip.vbs" %UPDATE_PACKAGE_LOCAL%
if exist "%~dp0\%UPDATE_PACKAGE_LOCAL%" del /q "%~dp0\%UPDATE_PACKAGE_LOCAL%" >nul 2>nul
if not exist "%~dp0\golem" (
    cscript.exe "%UTILS_DIR%\notify.vbs" "Error extracting update."
    goto END
)

if exist "%UTILS_DIR%" rd /S /Q "%UTILS_DIR%"

set "i="
for /F "delims=" %%i in ('dir /b "%~dp0\golem\"') do (
    if /i not "%%~nxi"=="%~nx0" (
        move /Y "%~dp0\golem\%%i" "%~dp0"
    )
)

move /Y "%~dp0\golem\%~nx0" "%UPDATED_SCRIPT%"
rd /S /Q "%~dp0\golem"

set LOG_PATH="%LOG_PATH%"
set SCRIPT="%UPDATED_SCRIPT%"

if "%*"=="" (
    start cmd /c "%SCRIPT% --gui >> %LOG_PATH% 2>&1"
) else (
    start cmd /c "%SCRIPT% %* >> %LOG_PATH% 2>&1"
)

copy /b/v/y "%UPDATED_SCRIPT%" "%~dp0\%~nx0"
:END
