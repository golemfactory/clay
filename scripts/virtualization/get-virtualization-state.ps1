$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$HyperVModule = @(Get-Module -ListAvailable hyper-v).Name | Get-Unique
# Is Hyper-V module installed?
If ($HyperVModule -eq "Hyper-V") {
    # Is Hyper-V management service running?
    try {
        Get-Process -Name vmms | Out-Null
        return "True"
    } catch { }
}

# Is hardware virtualization available and enabled?
$SystemInfo = (GWMI Win32_Processor)
return $SystemInfo.VMMonitorModeExtensions -and $SystemInfo.VirtualizationFirmwareEnabled
