$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$RunAsAdminScript = (AI_GetMsiProperty AI_RUN_AS_ADMIN_FILE)
"RunAsAdminScript: " + $RunAsAdminScript
$PrepareDockerScript = (AI_GetMsiProperty AI_PREPARE_DOCKER_FILE)
"PrepareDockerScript: " + $PrepareDockerScript
$CreateShareScript = (AI_GetMsiProperty AI_CREATESHARE_FILE)
"CreateShareScript: " + $CreateShareScript
$currentUserName = (AI_GetMsiProperty LogonUser)
"currentUserName: " + $currentUserName



# FIXME: LocalAppDataFolder property points to admin's AppData folder
# $AppDataDir = (AI_GetMsiProperty LocalAppDataFolder)
# For now we use the default temp folder used by the installer
$pathList = $RunAsAdminScript -split "\\Temp"
$AppDataDir = $pathList[0]
"AppDataDir: " + $AppDataDir

&"$RunAsAdminScript" -ScriptPath "$PrepareDockerScript" `
    -ScriptParams "-createShareScript `"$CreateShareScript`" -appDataDir `"$AppDataDir`" -currentUserName `"$currentUserName`""
