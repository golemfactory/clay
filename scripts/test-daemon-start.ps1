"Ensure hyperg is started"

New-Variable -Name hypergDir -Value C:\BuildResources\hyperg
New-Variable -Name workDir -Value C:\Users\buildbot-worker

$HyperdriveProcess = Get-Process hyperg -ErrorAction SilentlyContinue

if ($HyperdriveProcess) {
  Stop-Process -Id $HyperdriveProcess.Id
}

"Starting..."

$env:Path += ";$hypergDir"
$env:SEE_MASK_NOZONECHECKS = 1

$HyperdriveProcess = Start-Process $hypergDir\hyperg.exe -WorkingDirectory $workDir -PassThru

$HyperdriveProcess

$HyperdriveProcess.Id | Out-File .test-daemon-hyperg.pid
