$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

return (gwmi Win32_ComputerSystem).HypervisorPresent
