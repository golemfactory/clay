$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

# Is Hyper-V module installed?
$HyperVModule = @(Get-Module -ListAvailable hyper-v).Name | Get-Unique
If (!($HyperVModule -eq "Hyper-V")) {
    return "False"
}

# Is Hyper-V management service running?
try {
    Get-Process -Name vmms | Out-Null
} catch {
    return "False"
}

return "True"
