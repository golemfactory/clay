SET working_dir=%cd%
SET golem_repo=%working_dir%
SET tmp_folder=%golem_repo%\Installer\Installer_Win\install_tmp
SET resource_dir=C:\BuildResources

echo "Collecting version information"
IF NOT EXIST "%golem_repo%\golem\RELEASE-VERSION" EXIT /B
SET /P golem_version=<%golem_repo%\golem\RELEASE-VERSION

echo "Creating tmp folder '%tmp_folder%'"
REM Create tmp folder if not exists
IF NOT EXIST "%tmp_folder%" (
	md %tmp_folder%
	IF /I "%ERRORLEVEL%" NEQ "0" (
		ECHO execution failed
		PAUSE
		EXIT /B
	)
)


echo "Cleaning tmp folder"
REM Clean tmp folder if not exists
cd /d %tmp_folder%
IF /I "%ERRORLEVEL%" NEQ "0" (
    ECHO execution failed
	PAUSE
    EXIT /B
)
FOR /F "delims=" %%i IN ('DIR /b') DO (RMDIR "%%i" /s/q || DEL "%%i" /s/q)


echo "copy golem-dist '%golem_repo%\dist\golem-%golem_version%'"
REM golem-dist
IF NOT EXIST "%golem_repo%\dist\golem-%golem_version%" EXIT /B
XCOPY %golem_repo%\dist\golem-%golem_version%\. . /s /e


echo "copy win-unpacked"
REM electron
IF NOT EXIST "%resource_dir%\win-unpacked" EXIT /B
XCOPY %resource_dir%\win-unpacked\. . /s /e


echo "copy openssl"
REM openssl
IF NOT EXIST "%golem_repo%\Installer\Installer_Win\deps\OpenSSL" EXIT /B
XCOPY %golem_repo%\Installer\Installer_Win\deps\OpenSSL\. . /s /e


echo "copy hyperg"
REM hyperg
IF NOT EXIST "%resource_dir%\hyperg\" EXIT /B
XCOPY %resource_dir%\hyperg\. . /s /e

echo "Finished, back to original dir '%working_dir%'"

cd %working_dir%

PAUSE
