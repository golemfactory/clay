param(
    [Parameter(Mandatory=$true)] [string] $Interface
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

(Get-NetIPAddress -InterfaceAlias "*$Interface*" -AddressFamily IPv4).IPAddress | Write-Output