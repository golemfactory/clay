$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$CurrentUserName = (AI_GetMsiProperty USERNAME)
# FIXME: LocalAppDataFolder property points to admin's AppData folder
$AppDataDir = (AI_GetMsiProperty LocalAppDataFolder)

$RunAsAdminScript = (AI_GetMsiProperty AI_RUN_AS_ADMIN_FILE)
"RunAsAdminScript: " + $RunAsAdminScript
$PrepareDockerScript = (AI_GetMsiProperty AI_PREPARE_DOCKER_FILE)
"PrepareDockerScript: " + $PrepareDockerScript
$CreateShareScript = (AI_GetMsiProperty AI_CREATESHARE_FILE)
"CreateShareScript: " + $CreateShareScript

&"$RunAsAdminScript" -ScriptPath "$PrepareDockerScript" `
    -ScriptParams "-createShareScript `"$CreateShareScript`" -appDataDir `"$AppDataDir`" -currentUserName `"$currentUserName`""
