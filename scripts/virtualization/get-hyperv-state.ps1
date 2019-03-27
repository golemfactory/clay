$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$IsHypervisorPresent = (gwmi Win32_ComputerSystem).HypervisorPresent

if ($IsHypervisorPresent) {
    $HyperVServices = @("vmms", "vmcompute")

    try {
        foreach ($Service in $HyperVServices) {
            if ((Get-Service -Name $Service).Status -ne "Running") {
                return "False"
            }
        }

        return "True"
    } catch { }
}

return "False"
