$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

$DefaultVSwitchId = "c08cb7b8-9b3c-408e-8e30-5e16a3aeb444"
(Get-VMSwitch -Id $DefaultVSwitchId).Name | Write-Output
