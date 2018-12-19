param(
    [Parameter(Mandatory=$true)] [String] $VMName,
    [Int32] $IPTimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8

Start-VM -Name $VMName

# Wait until the VM has an IP address assigned
$timer = [System.Diagnostics.Stopwatch]::StartNew()
while (-not (Get-VM -Name $VMName).NetworkAdapters[0].IPAddresses[0]) {
    Start-Sleep -Milliseconds 500
    if ($timer.Elapsed.Seconds -gt $IPTimeoutSeconds) {
        throw "Waiting for IP timed out"
    }
}
$timer.Stop()

docker-machine env $VMName | Invoke-Expression
docker info
