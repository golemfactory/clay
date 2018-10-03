param(
    [Parameter(Mandatory=$true)] [string] $Interface
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

# "Add Golem Docker network switch"
$Interface = "Golem Switch"
$vmSwitch = Get-VMSwitch | ?{$_.name -eq "*$Interface*"}
# "vmSwitch:" + $vmSwitch
if( ! $vmSwitch )
{
	$vmSwitch = New-VMSwitch -Name "*$Interface*" -AllowManagementOS $True -NetAdapterName 'Ethernet'
	# "vmSwitch:" + $vmSwitch
	if ( ! $vmSwitch )
	{
			# "Installer failed to add hyperv switch:" + $vmSwitchName
			exit 1
	}
}

(Get-NetIPAddress -InterfaceAlias "*$Interface*" -AddressFamily IPv4).IPAddress | Write-Output
