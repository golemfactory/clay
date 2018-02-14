SET working_dir=%cd%
SET tmp_folder=%working_dir%\install_tmp
SET golem_repo=%working_dir%\..\..
SET /p golem_version=<%golem_repo%\golem\RELEASE-VERSION
SET resource_dir=C:\BuildResources


REM Create tmp folder if not exists
IF NOT EXIST "%tmp_folder%" (
	md %tmp_folder%
	IF /I "%ERRORLEVEL%" NEQ "0" (
		ECHO execution failed
		PAUSE
		EXIT /B
	)
)


REM Clean tmp folder if not exists
cd /d %tmp_folder%
IF /I "%ERRORLEVEL%" NEQ "0" (
    ECHO execution failed
	PAUSE
    EXIT /B
)
FOR /F "delims=" %%i IN ('DIR /b') DO (RMDIR "%%i" /s/q || DEL "%%i" /s/q)


REM golem-dist
IF NOT EXIST "%golem_repo%\dist\golem-%golem_version%" EXIT /B
XCOPY %golem_repo%\dist\golem-%golem_version%\. . /s /e


REM electron
IF NOT EXIST "%resource_dir%\win-unpacked" EXIT /B
XCOPY %resource_dir%\win-unpacked\. . /s /e


REM openssl
IF NOT EXIST "%golem_repo%\Installer\Installer_Win\deps\OpenSSL" EXIT /B
XCOPY %golem_repo%\Installer\Installer_Win\deps\OpenSSL\. . /s /e


REM hyperg
IF NOT EXIST "%resource_dir%\hyperg\" EXIT /B
XCOPY %resource_dir%\hyperg\. . /s /e

cd %working_dir%

PAUSE