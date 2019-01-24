$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$HyperVModule = @(Get-Module -ListAvailable hyper-v).Name | Get-Unique
If ($HyperVModule -eq "Hyper-V") {
    return "True"
}

$SystemInfo = (GWMI Win32_Processor)
return $SystemInfo.VMMonitorModeExtensions -and $SystemInfo.VirtualizationFirmwareEnabled
