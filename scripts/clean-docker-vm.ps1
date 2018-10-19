# Block for declaring the script parameters.
Param(
  $hasInstalled = (AI_GetMsiProperty AI_MISSING_PREREQS),
  $pfSFFolder = (AI_GetMsiProperty ProgramFiles64Folder)
)
<#
FIXME: VirtualBox is disabled, to be fixed in #3476
"Fix vbox install..."
# This is to make sure the virtualbox driver is installed properly (bug in install of vbox)
$infInstallPath = "$Env:SystemRoot\System32\InfDefaultInstall.exe"
$vboxdrvInfPath = "`"$Env:Programfiles\Oracle\VirtualBox\drivers\vboxdrv\VBoxDrv.inf`""
try {
	& $infInstallPath $vboxdrvInfPath
} catch {
	LogWrite ("Caught the exception")
	LogWrite ($Error[0].Exception)
}

try {
	Set-ItemProperty HKLM:\system\currentcontrolset\services\vboxdrv -Name ImagePath -Value "\??\$Env:Programfiles\Oracle\VirtualBox\drivers\vboxdrv\VBoxDrv.sys"
} catch {
	LogWrite ("Caught the exception")
	LogWrite ($Error[0].Exception)
}

try {
  Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Services\VBoxDrv" -Name "DelayedAutostart" -Value 1 -Type DWORD
} catch {
	LogWrite ("Caught the exception")
	LogWrite ($Error[0].Exception)
}

try {
	Start-Service vboxdrv
} catch {
	LogWrite ("Caught the exception")
	LogWrite ($Error[0].Exception)
}

"Done"
#>
"Clean Docker Machine..."
# TODO: Change to docker or docker-machine updated, always execute this time from TB -> binaries.
#if ( -Not ( $hasInstalled.indexof("Docker") = -1 ))
#{
$dockerRmCmd = """" + $pfSFFolder + "Docker Toolbox\docker-machine.exe"" rm -f golem"
cmd.exe /c $dockerRmCmd
#}

"Done"
