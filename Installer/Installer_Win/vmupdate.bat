docker-machine inspect golem 2>&1 > NUL
IF "%ERRORLEVEL%"=="0" ( docker-machine rm golem -y )
%WinDir%\System32\pnputil.exe -i -a "C:\Program Files\Oracle\VirtualBox\drivers\vboxdrv\VBoxDrv.inf"
