$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

# Is hardware virtualization available and enabled?
$SystemInfo = (GWMI Win32_Processor)
return $SystemInfo.VMMonitorModeExtensions -and $SystemInfo.VirtualizationFirmwareEnabled
