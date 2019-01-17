$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$SystemInfo = (GWMI Win32_Processor)
return $SystemInfo.VMMonitorModeExtensions -and $SystemInfo.VirtualizationFirmwareEnabled
